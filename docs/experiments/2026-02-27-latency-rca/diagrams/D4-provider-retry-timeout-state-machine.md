# D4 Provider Retry/Timeout State Machine (AS-IS)

```mermaid
stateDiagram-v2
  [*] --> InitialState
  state "Initial State" as InitialState
  InitialState: Request enters OpenAIProvider.generate
  InitialState: max_retries from env/provider
  InitialState: sdk timeout and sdk retries from env
  InitialState: max_total_seconds guard

  InitialState --> CircuitCheck
  CircuitCheck --> CircuitOpen: circuit breaker denies
  CircuitOpen --> Failed

  CircuitCheck --> AttemptLoop: circuit allows

  state AttemptLoop {
    [*] --> AttemptStart
    AttemptStart --> TimeBudgetCheck
    TimeBudgetCheck --> BudgetExceeded: elapsed >= max_total_seconds
    BudgetExceeded --> ExitLoop

    TimeBudgetCheck --> CallSDK
    CallSDK --> ParsePayload: response received

    ParsePayload --> Success: strict JSON parse OK
    ParsePayload --> JsonDecodeError: invalid JSON
    ParsePayload --> ApiError: other exception

    JsonDecodeError --> LengthEmptyBump: finish_reason=length and empty output
    LengthEmptyBump --> BackoffDelay
    JsonDecodeError --> RepairPromptAppend
    RepairPromptAppend --> BackoffDelay

    ApiError --> RetryableCheck
    RetryableCheck --> BackoffDelay: retryable && attempts left
    RetryableCheck --> ExitLoop: non-retryable or exhausted

    BackoffDelay --> AttemptStart
    Success --> [*]
    ExitLoop --> [*]
  }

  AttemptLoop --> Completed: success
  AttemptLoop --> Failed: exhausted or budget exceeded
  Completed --> [*]
  Failed --> [*]
```

## Legend
- SDK layer: `AsyncOpenAI(... timeout, max_retries ...)`
- Provider layer retries: `for attempt in range(self.max_retries)`
- Additional amplification branch: completion budget bump on `finish_reason=length`
