def send_request(request: dict) -> dict:
    if not request.get('bounded'):
        return {'accepted': False, 'reason': 'unbounded_request'}
    return {'accepted': True, 'execution_id': 'fake-exec-001'}
