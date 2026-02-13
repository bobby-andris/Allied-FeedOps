import { describe, expect, it } from 'vitest'

import { resolveDefaultFinishSelection } from '../lifestyle-image-selection'

describe('resolveDefaultFinishSelection', () => {
  it('keeps explicit selected finish when available', () => {
    const finish = resolveDefaultFinishSelection({
      selectedFinish: 'Satin Nickel',
      imagesByFinish: {
        'Polished Chrome': [{ user_selected: false, ai_selected: false }],
        'Satin Nickel': [{ user_selected: false, ai_selected: false }],
      },
    })

    expect(finish).toBe('Satin Nickel')
  })

  it('falls back to user-selected finish when explicit selection is missing', () => {
    const finish = resolveDefaultFinishSelection({
      selectedFinish: null,
      imagesByFinish: {
        'Polished Chrome': [{ user_selected: false, ai_selected: false }],
        'Satin Nickel': [{ user_selected: true, ai_selected: false }],
      },
    })

    expect(finish).toBe('Satin Nickel')
  })

  it('falls back to AI-selected finish when no user selection exists', () => {
    const finish = resolveDefaultFinishSelection({
      selectedFinish: null,
      imagesByFinish: {
        'Polished Chrome': [{ user_selected: false, ai_selected: true }],
        'Satin Nickel': [{ user_selected: false, ai_selected: false }],
      },
    })

    expect(finish).toBe('Polished Chrome')
  })

  it('falls back to first available finish as last resort', () => {
    const finish = resolveDefaultFinishSelection({
      selectedFinish: null,
      imagesByFinish: {
        'Polished Chrome': [{ user_selected: false, ai_selected: false }],
        'Satin Nickel': [{ user_selected: false, ai_selected: false }],
      },
    })

    expect(finish).toBe('Polished Chrome')
  })
})
