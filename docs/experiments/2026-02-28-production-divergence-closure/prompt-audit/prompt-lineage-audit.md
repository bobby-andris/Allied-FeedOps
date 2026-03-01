# Prompt Lineage Audit

## Job ID Behavior

Single-route `/regenerate` executions are synchronous and return `RegenerateResponse`, so a missing `job_id` is expected for successful inline single Google title/description runs.

Batch and hybrid routes create background job rows and therefore return `job_id` values.

## Route Prompt Matrix

### single Google title
- Route: `/regenerate`
- Job ID expected: `False`
- Task graph: `TITLE`
- System prompt source: build_task_system_prompt(TaskSpec[TITLE]) -> get_platform_system_prompt('google')
- User prompt source: build_task_prompt(TaskSpec[TITLE]) -> build_core_prompt(...) + optional persistent corrections + task output contract
- Stored prompt rows:
  - google/title base generation

### single Google description
- Route: `/regenerate`
- Job ID expected: `False`
- Task graph: `DESCRIPTION_BASE, FINISH_SENTENCES`
- System prompt source: base row uses get_platform_system_prompt('google'); finish subcall uses get_platform_system_prompt('finish')
- User prompt source: base row uses build_core_prompt(...) + optional persistent corrections + task output contract; finish subcall uses build_finish_prompt(...)
- Stored prompt rows:
  - google/description base generation
  - finish subcall is executed but not persisted as its own regeneration_history row

### batch Google title
- Route: `/batch-optimize`
- Job ID expected: `True`
- Task graph: `TITLE`
- System prompt source: build_task_system_prompt(TaskSpec[TITLE]) -> get_platform_system_prompt('google')
- User prompt source: build_task_prompt(TaskSpec[TITLE]) -> build_core_prompt(...) + task output contract
- Stored prompt rows:
  - google/title base generation

### batch Google description
- Route: `/batch-optimize`
- Job ID expected: `True`
- Task graph: `DESCRIPTION_BASE, FINISH_SENTENCES`
- System prompt source: base row uses get_platform_system_prompt('google'); finish subcall uses get_platform_system_prompt('finish')
- User prompt source: base row uses build_core_prompt(...) + task output contract; finish subcall uses build_finish_prompt(...)
- Stored prompt rows:
  - google/description base generation
  - finish subcall is executed but not persisted as its own regeneration_history row

### hybrid Google title
- Route: `/hybrid-generate`
- Job ID expected: `True`
- Task graph: `shared TITLE, VARIANT_ADAPTATION`
- System prompt source: both rows use get_platform_system_prompt('google') via build_task_system_prompt(...)
- User prompt source: base row uses build_core_prompt(...) + task output contract; variant row uses build_variant_adaptation_prompt(..., include_finish_sentences=False)
- Stored prompt rows:
  - google/title base generation
  - google/title variant adaptation

### hybrid Google description
- Route: `/hybrid-generate`
- Job ID expected: `True`
- Task graph: `shared DESCRIPTION_BASE, shared FINISH_SENTENCES, VARIANT_ADAPTATION`
- System prompt source: base row uses get_platform_system_prompt('google'); finish subcall uses get_platform_system_prompt('finish'); variant row uses get_platform_system_prompt('google')
- User prompt source: base row uses build_core_prompt(...) + task output contract; finish subcall uses build_finish_prompt(...); variant row uses build_variant_adaptation_prompt(..., include_finish_sentences=False)
- Stored prompt rows:
  - google/description base generation
  - google/description variant adaptation
  - finish subcall is executed but not persisted as its own regeneration_history row

## Row-by-Row Prompt Parity

| Case | Request ID | Stored rows | All rows matched | Notes |
| --- | --- | ---: | --- | --- |
| single_google_title | `fe2510cb-b759-4a06-a5df-c58309f1e8a4` | 1 | yes | synchronous route; no job_id expected |
| single_google_description | `15d179be-8dec-4cbe-8b24-01fafd8c1a15` | 1 | yes | synchronous route; no job_id expected; finish generation executes but is not stored as a separate prompt row |
| batch_google_title | `b9cb52c9-6654-4a50-9fac-e39a437118ff` | 1 | yes | stored prompt rows match source exactly |
| batch_google_description | `16040988-905e-42fa-93e1-225447fb5b79` | 1 | yes | finish generation executes but is not stored as a separate prompt row |
| hybrid_google_title | `aada2ba2-b0fb-4194-a200-d126d48f4082` | 2 | yes | stored prompt rows match source exactly |
| hybrid_google_description | `99c5f032-86fb-4cf1-b115-7f3e714fd216` | 2 | yes | finish generation executes but is not stored as a separate prompt row |

### single_google_title

- Route: `/regenerate`
- Request ID: `fe2510cb-b759-4a06-a5df-c58309f1e8a4`
- Job ID expected: `False`
- Job ID: `none`
- Stored prompt rows found: `1`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CL-55` | `google` | `title` | `with_feedback` | yes | yes | yes | yes | yes |

### single_google_description

- Route: `/regenerate`
- Request ID: `15d179be-8dec-4cbe-8b24-01fafd8c1a15`
- Job ID expected: `False`
- Job ID: `none`
- Stored prompt rows found: `1`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CL-55` | `google` | `description` | `with_feedback` | yes | yes | yes | yes | yes |

### batch_google_title

- Route: `/batch-optimize`
- Request ID: `b9cb52c9-6654-4a50-9fac-e39a437118ff`
- Job ID expected: `True`
- Job ID: `f3a17184-fde9-41c8-9414-bc6bf873f1a3`
- Stored prompt rows found: `1`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CL-55` | `google` | `title` | `full_generation_v2` | yes | yes | yes | yes | yes |

### batch_google_description

- Route: `/batch-optimize`
- Request ID: `16040988-905e-42fa-93e1-225447fb5b79`
- Job ID expected: `True`
- Job ID: `ef371ff2-b2c8-4d03-ac99-74ecb5fc36b1`
- Stored prompt rows found: `1`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CL-55` | `google` | `description` | `full_generation_v2` | yes | yes | yes | yes | yes |

### hybrid_google_title

- Route: `/hybrid-generate`
- Request ID: `aada2ba2-b0fb-4194-a200-d126d48f4082`
- Job ID expected: `True`
- Job ID: `c8119d75-e24c-4f24-9e47-7ae15cc072ee`
- Stored prompt rows found: `2`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1033/18` | `google` | `title` | `full_generation_v2` | yes | yes | yes | yes | yes |
| `1033/24` | `google` | `title` | `variant-adaptation-v2` | yes | yes | yes | yes | yes |

### hybrid_google_description

- Route: `/hybrid-generate`
- Request ID: `99c5f032-86fb-4cf1-b115-7f3e714fd216`
- Job ID expected: `True`
- Job ID: `cbc104f5-f7fd-4e87-8905-27ec6e6e9bea`
- Stored prompt rows found: `2`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1033/18` | `google` | `description` | `full_generation_v2` | yes | yes | yes | yes | yes |
| `1033/24` | `google` | `description` | `variant-adaptation-v2` | yes | yes | yes | yes | yes |
