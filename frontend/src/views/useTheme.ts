import { useEffect, useState } from "react";

type Theme = "light" | "dark";
const storageKey = "slackline-theme";

function storedTheme(): Theme | null {
  try {
    const value = localStorage.getItem(storageKey);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

function systemTheme(): Theme {
  try {
    return matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  } catch {
    return "light";
  }
}

// No stored choice follows the system setting through the CSS media query.
export function useTheme() {
  const [choice, setChoice] = useState<Theme | null>(storedTheme);
  const [system, setSystem] = useState<Theme>(systemTheme);
  useEffect(() => {
    let media: MediaQueryList;
    try {
      media = matchMedia("(prefers-color-scheme: dark)");
    } catch {
      return;
    }
    const update = () => setSystem(media.matches ? "dark" : "light");
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (choice) document.documentElement.dataset.theme = choice;
    else delete document.documentElement.dataset.theme;
  }, [choice]);
  const theme = choice ?? system;
  const toggleTheme = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setChoice(next);
    try {
      localStorage.setItem(storageKey, next);
    } catch {
      // Private windows can block storage. The choice still applies to this visit.
    }
  };
  return { theme, toggleTheme };
}
