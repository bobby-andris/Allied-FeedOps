export const PIPELINE_URL_ENV_VAR = 'FEEDOPS_PIPELINE_URL'

export const PIPELINE_URL_MISSING_MESSAGE =
  'Content generation pipeline is not configured (FEEDOPS_PIPELINE_URL not set)'

export function getRequiredPipelineUrl(): string {
  const pipelineUrl = process.env.FEEDOPS_PIPELINE_URL?.trim()
  if (!pipelineUrl) {
    throw new Error(PIPELINE_URL_MISSING_MESSAGE)
  }
  return pipelineUrl.replace(/\/$/, '')
}
