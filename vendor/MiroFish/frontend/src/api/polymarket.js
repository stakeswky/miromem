import service from './index'

/**
 * 获取 Polymarket 热门事件列表
 * @param {Object} params - { limit, offset, tag, search }
 */
export function getPolymarketEvents(params = {}) {
  return service({
    url: '/api/polymarket/events',
    method: 'get',
    params
  })
}

/**
 * 获取单个事件详情
 * @param {String} eventId
 */
export function getPolymarketEvent(eventId) {
  return service({
    url: `/api/polymarket/events/${eventId}`,
    method: 'get'
  })
}
