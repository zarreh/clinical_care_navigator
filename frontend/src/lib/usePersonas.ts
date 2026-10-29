"use client";

import { useEffect, useState } from "react";

import { ApiError, listPersonas, type Persona } from "./api";

type State = { personas: Persona[]; loading: boolean; error: string | null };

/** The demo patients, fetched once per mount. */
export function usePersonas(): State {
  const [state, setState] = useState<State>({ personas: [], loading: true, error: null });
  useEffect(() => {
    let cancelled = false;
    listPersonas()
      .then((personas) => !cancelled && setState({ personas, loading: false, error: null }))
      .catch(
        (error: unknown) =>
          !cancelled &&
          setState({
            personas: [],
            loading: false,
            error: error instanceof ApiError ? error.message : "Could not load the demo patients.",
          })
      );
    return () => {
      cancelled = true;
    };
  }, []);
  return state;
}
