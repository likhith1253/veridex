/**
 * Forensic Investigation Dossier API Service.
 * Verified against FastAPI routes in app/api/routes/investigations.py.
 */

import { apiClient } from "./client";
import type { InvestigationDossier } from "@/types/investigation";

export const investigationsApi = {
  /** Retrieve comprehensive AI investigation & evidence dossier for an entity */
  getDossier: async (id: string): Promise<InvestigationDossier> => {
    return apiClient<InvestigationDossier>(`/api/v1/investigations/${encodeURIComponent(id)}`);
  },
};
