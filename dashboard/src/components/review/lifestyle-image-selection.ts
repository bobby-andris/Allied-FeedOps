interface LifestyleImageSelectionFlags {
  user_selected: boolean
  ai_selected: boolean
}

interface ResolveDefaultFinishSelectionInput {
  selectedFinish: string | null
  imagesByFinish: Record<string, LifestyleImageSelectionFlags[]>
}

export function resolveDefaultFinishSelection(
  input: ResolveDefaultFinishSelectionInput,
): string | null {
  const { selectedFinish, imagesByFinish } = input

  if (selectedFinish && imagesByFinish[selectedFinish]) {
    return selectedFinish
  }

  const finishes = Object.keys(imagesByFinish)
  if (finishes.length === 0) {
    return null
  }

  const userSelectedFinish = finishes.find((finish) =>
    imagesByFinish[finish]?.some((image) => image.user_selected),
  )
  if (userSelectedFinish) {
    return userSelectedFinish
  }

  const aiSelectedFinish = finishes.find((finish) =>
    imagesByFinish[finish]?.some((image) => image.ai_selected),
  )
  if (aiSelectedFinish) {
    return aiSelectedFinish
  }

  return finishes[0]
}
