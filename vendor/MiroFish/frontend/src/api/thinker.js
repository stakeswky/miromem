import service from './index.js'

/**
 * Create a Thinker job from either a JSON payload or FormData.
 * Multipart boundaries are left to Axios/browser handling.
 * @param {Object|FormData} payload
 * @returns {Promise}
 */
export function createThinkerJob(payload) {
  return service.post('/api/v1/thinker/jobs', payload)
}

/**
 * Fetch the latest Thinker job state.
 * @param {string} jobId
 * @returns {Promise}
 */
export function getThinkerJob(jobId) {
  return service.get(`/api/v1/thinker/jobs/${jobId}`)
}

/**
 * Materialize a Thinker result into downstream simulation inputs.
 * @param {Object} payload
 * @returns {Promise}
 */
export function materializeThinkerJob(payload) {
  return service.post('/api/v1/thinker/materialize', payload)
}

/**
 * Retry a failed Thinker job.
 * @param {string} jobId
 * @returns {Promise}
 */
export function retryThinkerJob(jobId) {
  return service.post(`/api/v1/thinker/jobs/${jobId}/retry`)
}

/**
 * Skip a terminal Thinker job so the upload flow can continue.
 * @param {string} jobId
 * @returns {Promise}
 */
export function skipThinkerJob(jobId) {
  return service.post(`/api/v1/thinker/jobs/${jobId}/skip`)
}
