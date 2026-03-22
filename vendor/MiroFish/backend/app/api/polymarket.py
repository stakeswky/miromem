"""
Polymarket API 代理蓝图
代理 Gamma API 避免前端跨域，提供事件列表和详情接口
"""

import requests
from flask import Blueprint, request, jsonify

polymarket_bp = Blueprint('polymarket', __name__)

GAMMA_API = "https://gamma-api.polymarket.com"


@polymarket_bp.route('/events', methods=['GET'])
def list_events():
    """获取 Polymarket 热门事件列表"""
    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)
    tag = request.args.get('tag', '')
    search = request.args.get('search', '')

    params = {
        'limit': min(limit, 50),
        'offset': offset,
        'active': 'true',
        'closed': 'false',
        'order': 'volume24hr',
        'ascending': 'false',
    }
    if tag:
        params['tag'] = tag
    if search:
        params['_q'] = search

    try:
        resp = requests.get(f"{GAMMA_API}/events", params=params, timeout=15)
        resp.raise_for_status()
        events = resp.json()

        # 精简返回字段
        result = []
        for ev in events:
            markets = []
            for m in ev.get('markets', []):
                markets.append({
                    'question': m.get('question', ''),
                    'outcomes': m.get('outcomes', ''),
                    'outcomePrices': m.get('outcomePrices', ''),
                    'volume24hr': m.get('volume24hr', 0),
                })
            result.append({
                'id': ev.get('id'),
                'title': ev.get('title', ''),
                'description': ev.get('description', ''),
                'slug': ev.get('slug', ''),
                'image': ev.get('image', ''),
                'volume24hr': ev.get('volume24hr', 0),
                'liquidity': ev.get('liquidity', 0),
                'startDate': ev.get('startDate', ''),
                'endDate': ev.get('endDate', ''),
                'markets': markets,
            })

        return jsonify({'success': True, 'data': result})
    except requests.RequestException as e:
        return jsonify({'success': False, 'error': str(e)}), 502


@polymarket_bp.route('/events/<event_id>', methods=['GET'])
def get_event(event_id):
    """获取单个事件详情"""
    try:
        resp = requests.get(f"{GAMMA_API}/events/{event_id}", timeout=15)
        resp.raise_for_status()
        return jsonify({'success': True, 'data': resp.json()})
    except requests.RequestException as e:
        return jsonify({'success': False, 'error': str(e)}), 502
