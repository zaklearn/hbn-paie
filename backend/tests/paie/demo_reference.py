"""Constantes de démonstration reprises À L'IDENTIQUE de paie-bulletins (src/services/demo.py).

Portage S1 : ``demo.py`` dépend de SQLite et des services, portés en S2. Ses trois constantes
(DEMO_COMPANY, DEMO_EMPLOYEE, REFERENCE_INPUT) sont recopiées ici sans modification ;
``test_port_fidelity.py`` vérifie l'identité du bloc avec l'original. En S2, les imports
reviendront à ``app.paie.services.demo`` (demo.py porté tel quel) et ce fichier sera retiré.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

from app.paie.core.models.entities import Company, Employee
from app.paie.core.models.payroll import MonthlyInput

DEMO_COMPANY = Company(
    raison_sociale="SOCIÉTÉ EXEMPLE SARL",
    adresse="12, rue de l'Exemple",
    ville="Ville-Exemple",
    ice="000000000000000",
    cnss_employeur="0000000",
    rc="RC-EXEMPLE",
    identifiant_fiscal="IF-EXEMPLE",
)

DEMO_EMPLOYEE = Employee(
    matricule="0001",
    nom="EXEMPLE",
    prenom="Salarié",
    date_naissance=date(1990, 1, 1),
    cin="XX000000",
    cnss="000000000",
    situation_familiale="Célibataire",
    nb_personnes_charge=0,
    date_embauche=date(2026, 7, 1),
    fonction="Employé",
    mode_paiement="Virement",
    banque="BANQUE EXEMPLE",
    compte_bancaire="000 000 0000000000000000 00",
)

# Saisie!B21:D30 du classeur de référence.
REFERENCE_INPUT = MonthlyInput(
    salaire_base=D("5436.51"), jours_declares=D("26"), heures_sup=D("0"),
    prime_panier=D("930"), indemnite_transport=D("500"), indemnite_representation=D("500"),
    autre_prime=D("0"), conges_reliquat=D("0"), conges_acquis=D("1.5"), conges_pris=D("0"),
)
