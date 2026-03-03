# OpenAI Raw Failure Proof (CL-55, Google)

## Reproduction setup
- SKU: `CL-55`
- Platform: `google`
- Model: `gpt-5.2`
- Reasoning effort: `medium`
- Prompt path: current per-platform runtime prompt assembly

## A) Failing run at low cap (`max_completion_tokens=2400`)
Observed raw OpenAI response snapshot from provider (`last_response_snapshot`):

```json
{
  "id": "chatcmpl-DEBcKmXMlvdkSLYD2B8cTXMBdvB7l",
  "model": "gpt-5.2-2025-12-11",
  "finish_reason": "length",
  "content_chars": 0,
  "content_preview": "",
  "usage": {
    "prompt_tokens": 4167,
    "completion_tokens": 2400,
    "cached_tokens": 1664
  },
  "raw_response": {
    "choices": [
      {
        "finish_reason": "length",
        "message": {
          "content": ""
        }
      }
    ],
    "usage": {
      "completion_tokens": 2400,
      "prompt_tokens": 4167,
      "completion_tokens_details": {
        "reasoning_tokens": 2400
      },
      "prompt_tokens_details": {
        "cached_tokens": 1664
      }
    }
  }
}
```

Outcome:
- provider raised JSON decode failure on empty output
- this is a direct upstream response payload proving truncation-at-cap

## B) Successful rerun with raised cap (`max_completion_tokens=6000`)
Observed outcome from same prompt flow:
- `RESULT_OK`
- `google_title_len=80`
- `google_desc_len=711`

## Conclusion
The observed failure was caused by an insufficient completion cap under strict JSON + reasoning workload, not by fabricated parser behavior. The parser was correctly surfacing an empty model payload.
