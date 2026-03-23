export function getRequiredLiveEnv(name: string): string {
  const value = process.env[name]
  if (!value) {
    throw new Error(`Missing required live E2E environment variable: ${name}`)
  }
  return value
}

export function isLiveRun(): boolean {
  return process.env.PLAYWRIGHT_LIVE === '1'
}
