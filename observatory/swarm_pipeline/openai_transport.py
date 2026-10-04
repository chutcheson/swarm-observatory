"""Secret-safe, tool-free OpenAI Responses transport (Python standard library)."""
import json
import re
import socket
import urllib.error
import urllib.request
from pathlib import Path

API_ORIGIN = 'https://api.openai.com'
DEFAULT_KEY_FILE = '~/.keys/openai'
KEY_PATTERN = re.compile(r'(?<![\w-])sk-(?!ant-)[A-Za-z0-9_-]{20,}')

class APIError(RuntimeError):
    def __init__(self, message, *, retryable=False, usage=None, fatal=False):
        super().__init__(message)
        self.retryable = retryable
        self.usage = usage
        self.fatal = fatal

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def load_key(path=DEFAULT_KEY_FILE):
    """Read only the chosen file; never evaluate it or fall back to another key."""
    try:
        content = Path(path).expanduser().read_text()
    except OSError:
        raise APIError('OpenAI credential file is not readable.', fatal=True) from None
    candidates = list(dict.fromkeys(KEY_PATTERN.findall(content)))
    if len(candidates) != 1:
        raise APIError('OpenAI credential file must contain exactly one API key.', fatal=True)
    return candidates[0]

def safe_code(value):
    value = str(value or '')
    return value if re.fullmatch(r'[a-z_]{1,64}', value) else 'unspecified'

def request_json(path, payload, key_file, timeout, client_request_id):
    """The credential is sent only to the fixed OpenAI API origin; no redirects."""
    key = load_key(key_file)
    req = urllib.request.Request(API_ORIGIN + path,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), method='POST',
        headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json',
                 'X-Client-Request-Id': client_request_id})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
            raw = response.read(16_000_001)
            if len(raw) > 16_000_000:
                raise APIError('OpenAI response exceeded the transport size limit.')
            try:
                data = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise APIError('OpenAI returned a non-JSON response.') from None
            return data, response.headers.get('x-request-id')
    except urllib.error.HTTPError as exc:
        try:
            error = json.loads(exc.read(100_000)).get('error', {})
        except (ValueError, AttributeError):
            error = {}
        exc.close()
        code = safe_code(error.get('code')) if isinstance(error, dict) else 'unspecified'
        retryable = (exc.code in (408, 409, 429) or exc.code >= 500) and code != 'insufficient_quota'
        # Never retain raw server messages: authentication errors can echo key fragments.
        raise APIError(f'OpenAI API HTTP {exc.code} ({code}).', retryable=retryable,
                       fatal=exc.code in (401, 403, 404) or code == 'insufficient_quota') from None
    except (urllib.error.URLError, TimeoutError, socket.timeout):
        raise APIError('OpenAI API connection failed or timed out; usage is unknown.', retryable=True) from None

def normalized_usage(data):
    usage = data.get('usage')
    if not isinstance(usage, dict):
        return None
    out = {}
    for field in ('input_tokens', 'output_tokens', 'total_tokens'):
        value = usage.get(field)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            out[field] = value
    if 'input_tokens' not in out or 'output_tokens' not in out:
        return None
    for field, nested, key in [('cached_input_tokens','input_tokens_details','cached_tokens'),
                               ('reasoning_output_tokens','output_tokens_details','reasoning_tokens')]:
        value = (usage.get(nested) or {}).get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            out[field] = value
    return out

def complete(job, prompt, key_file=DEFAULT_KEY_FILE, timeout=720):
    instructions, marker, evidence = prompt.partition('\n\nEVIDENCE_DATA\n')
    if not marker:
        raise APIError('Worker prompt is missing its evidence boundary.')
    cfg = job['config']
    payload = {
        'model': cfg['model'], 'instructions': instructions,
        'input': 'EVIDENCE_DATA\n'+evidence, 'tools': [], 'store': False,
        'reasoning': {'effort': cfg['reasoning']},
        'service_tier': 'default',
        'max_output_tokens': cfg.get('max_output_tokens', 8000),
        'text': {'format': {'type':'json_schema', 'name':'swarm_'+job['stage'],
                            'strict':True, 'schema':job['schema']}},
    }
    data, request_id = request_json('/v1/responses', payload, key_file, timeout, job['attempt_id'])
    usage = normalized_usage(data)
    if data.get('status') != 'completed':
        reason = safe_code((data.get('incomplete_details') or {}).get('reason'))
        raise APIError('OpenAI response did not complete ('+reason+').', usage=usage)
    texts = []
    for item in data.get('output', []):
        if item.get('type') != 'message':
            continue
        for content in item.get('content', []):
            if content.get('type') == 'refusal':
                raise APIError('OpenAI declined this analysis request.', usage=usage)
            if content.get('type') == 'output_text':
                texts.append(content.get('text', ''))
    try:
        result = json.loads(''.join(texts))
    except (ValueError, TypeError):
        raise APIError('OpenAI returned no valid structured result.', usage=usage) from None
    return result, usage, {'backend':'openai', 'response_id':data.get('id'),
                           'request_id':request_id, 'model':data.get('model'),
                           'service_tier':data.get('service_tier'),
                           'max_output_tokens':payload['max_output_tokens']}
