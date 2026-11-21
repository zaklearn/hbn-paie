export type Role = 'superadmin' | 'user'
export interface User { id: number; username: string; display_name: string; role: Role }
export interface Employee {
  id: number; matricule: string; nom: string; prenom: string; date_naissance: string | null; cin: string;
  cnss: string; situation_familiale: string; nb_personnes_charge: number; date_embauche: string | null;
  date_sortie: string | null; fonction: string; departement: string; cimr: string; categorie: string;
  banque: string; compte_bancaire: string; adresse: string; mode_paiement: string; actif: boolean
}
export interface Issue { level: 'erreur' | 'avertissement'; field: string; message: string }
export type Amounts = Record<string, string>
export interface Payslip {
  id: number; employee_id: number; year: number; month: number; version: number; status: string;
  status_label: string; inputs: Amounts; result: Amounts | null; cumuls: Amounts | null;
  replaces_id: number | null; rectification_reason: string; closed_at: string | null; closed_by: string;
  parameter_set_id: number | null; employee_snapshot: Record<string, unknown> | null
}
export interface Echeance {
  id: number; employee_id: number; n: number; date_echeance: string; mois: string; type: string; montant: number;
  statut: string; rappel_j1: string; observations: string; date_paiement: string | null; annee: number;
  mois_num: number; version: number; paye: boolean; en_retard: boolean
}
