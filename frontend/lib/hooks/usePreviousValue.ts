import { useEffect, useRef } from "react";

/**
 * Tracks the previous render's value of a real fetched number so components
 * can compute a genuine delta (current vs previous fetch) without ever
 * fabricating a number. Returns `undefined` until a second distinct value has
 * been observed.
 */
export function usePreviousValue(value: number | null | undefined): number | undefined {
  const currentRef = useRef<number | undefined>(undefined);
  const previousRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (value === null || value === undefined || !Number.isFinite(value)) return;
    if (currentRef.current !== value) {
      previousRef.current = currentRef.current;
      currentRef.current = value;
    }
  }, [value]);

  return previousRef.current;
}
