export const TENT_THEMES = [
  { value: "fashion-edit", label: "Fashion Edit", accent: "#C0243C" },
  { value: "tech-hub", label: "Tech Hub", accent: "#2C8EFF" },
  { value: "snack-bar", label: "Snack Bar", accent: "#E88C1A" },
  { value: "ritual-corner", label: "Ritual Corner", accent: "#0FA29A" },
  { value: "gem-counter", label: "Gem Counter", accent: "#C8941A" },
  { value: "home-finds", label: "Home Finds", accent: "#C06830" }
] as const;

export type TentTheme = (typeof TENT_THEMES)[number]["value"];

export const DEFAULT_TENT_THEME: TentTheme = "fashion-edit";

export function isTentTheme(value: string): value is TentTheme {
  return TENT_THEMES.some((theme) => theme.value === value);
}
