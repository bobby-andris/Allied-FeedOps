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
  - finish/finish_sentences lineage row

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
  - finish/finish_sentences lineage row

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
  - finish/finish_sentences lineage row
  - google/description variant adaptation

## Row-by-Row Prompt Parity

| Case | Request ID | Stored rows | All rows matched | Notes |
| --- | --- | ---: | --- | --- |
| single_google_title | `0bcced58-8875-4f0d-bf07-555c0ce2306f` | 1 | yes | synchronous route; no job_id expected |
| single_google_description | `88a07424-755b-4481-be1b-8efcea9467c6` | 2 | yes | synchronous route; no job_id expected; finish generation persisted as first-class lineage row |
| batch_google_title | `a5ec6ac3-03e3-402c-8447-5572973559dc` | 1 | yes | stored prompt rows match source exactly |
| batch_google_description | `e5160cf0-bdbc-4076-9bfd-4c82e28dd751` | 2 | yes | finish generation persisted as first-class lineage row |
| hybrid_google_title | `89831fe5-4f3d-401f-94ee-db2b30cb01ae` | 2 | yes | stored prompt rows match source exactly |
| hybrid_google_description | `c304c08e-3729-4cf1-829b-cd5fddbf6e38` | 3 | yes | finish generation persisted as first-class lineage row |

### single_google_title

- Route: `/regenerate`
- Request ID: `0bcced58-8875-4f0d-bf07-555c0ce2306f`
- Job ID expected: `False`
- Job ID: `none`
- Stored prompt rows found: `1`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CL-55` | `google` | `title` | `with_feedback` | yes | yes | yes | yes | yes |

### single_google_description

- Route: `/regenerate`
- Request ID: `88a07424-755b-4481-be1b-8efcea9467c6`
- Job ID expected: `False`
- Job ID: `none`
- Stored prompt rows found: `2`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CL-55` | `google` | `description` | `with_feedback` | yes | yes | yes | yes | yes |
| `CL-55` | `finish` | `finish_sentences` | `with_feedback_finish_sentences` | yes | yes | yes | yes | yes |

### batch_google_title

- Route: `/batch-optimize`
- Request ID: `a5ec6ac3-03e3-402c-8447-5572973559dc`
- Job ID expected: `True`
- Job ID: `ce3f1f47-2ace-460b-a86e-60ced23d5845`
- Stored prompt rows found: `1`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CL-55` | `google` | `title` | `full_generation_v2` | yes | yes | yes | yes | yes |

### batch_google_description

- Route: `/batch-optimize`
- Request ID: `e5160cf0-bdbc-4076-9bfd-4c82e28dd751`
- Job ID expected: `True`
- Job ID: `cec8e4f2-10b6-45bd-a06c-1f75cd1555a4`
- Stored prompt rows found: `2`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CL-55` | `google` | `description` | `full_generation_v2` | yes | yes | yes | yes | yes |
| `CL-55` | `finish` | `finish_sentences` | `full_generation_v2_finish_sentences` | yes | yes | yes | yes | yes |

### hybrid_google_title

- Route: `/hybrid-generate`
- Request ID: `89831fe5-4f3d-401f-94ee-db2b30cb01ae`
- Job ID expected: `True`
- Job ID: `4cd6e728-f605-4767-b897-073a35c0d7dd`
- Stored prompt rows found: `2`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1033/18` | `google` | `title` | `full_generation_v2` | yes | yes | yes | yes | yes |
| `1033/24` | `google` | `title` | `variant-adaptation-v2` | yes | yes | yes | yes | yes |

### hybrid_google_description

- Route: `/hybrid-generate`
- Request ID: `c304c08e-3729-4cf1-829b-cd5fddbf6e38`
- Job ID expected: `True`
- Job ID: `fd3c4fa0-3058-4abc-9b38-a1ced5e7cb78`
- Stored prompt rows found: `3`
- All stored prompt rows matched source expectation: `True`

| SKU | Platform | Content | Mode | System | User | Prompt hash | Assembled hash | Canonical hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1033/18` | `google` | `description` | `full_generation_v2` | yes | yes | yes | yes | yes |
| `1033/18` | `finish` | `finish_sentences` | `full_generation_v2_finish_sentences` | yes | yes | yes | yes | yes |
| `1033/24` | `google` | `description` | `variant-adaptation-v2` | yes | yes | yes | yes | yes |
