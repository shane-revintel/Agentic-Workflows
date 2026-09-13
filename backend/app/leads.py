"""Lead source.

Leads are modeled on Bowtie / Salesbot.io output: an enriched contact plus a
"fit reason" and score explaining why they match your ICP. That context is what
makes a cold opener feel personal.

The provider is pluggable: a built-in sample set runs with zero setup, and a
``BowtieProvider`` placeholder shows where to plug in your Bowtie export/API
once credentials are available (set ``BOWTIE_API_KEY``).
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass
class Lead:
    id: str
    name: str
    title: str
    company: str
    industry: str = ""
    email: str = ""
    source: str = "Salesbot.io (Bowtie)"
    fit_reason: str = ""
    fit_score: int = 0
    notes: str = ""

    def as_dict(self) -> Dict:
        return asdict(self)

    def context_block(self) -> str:
        """A compact briefing the SDR agent can use to personalize outreach."""
        parts = [
            f"Name: {self.name}",
            f"Title: {self.title}",
            f"Company: {self.company}" + (f" ({self.industry})" if self.industry else ""),
        ]
        if self.fit_reason:
            parts.append(f"Why they fit (from {self.source}): {self.fit_reason}")
        if self.fit_score:
            parts.append(f"Fit score: {self.fit_score}/100")
        if self.notes:
            parts.append(f"Notes: {self.notes}")
        return "\n".join(parts)


SAMPLE_LEADS: List[Lead] = [
    Lead(
        id="l1",
        name="Jordan Lee",
        title="Head of Growth",
        company="Northstar Retail",
        industry="E-commerce",
        email="jordan.lee@northstarretail.example",
        fit_reason=(
            "Fast-growing DTC brand scaling paid acquisition; likely struggling to "
            "respond to and qualify inbound leads quickly enough."
        ),
        fit_score=88,
    ),
    Lead(
        id="l2",
        name="Priya Shah",
        title="VP of Sales",
        company="Apex Logistics",
        industry="Supply chain SaaS",
        email="priya.shah@apexlogistics.example",
        fit_reason=(
            "Mid-market SaaS with a growing SDR team; hiring reps signals pressure "
            "to book more meetings without adding headcount."
        ),
        fit_score=82,
    ),
    Lead(
        id="l3",
        name="Marcus Reed",
        title="Founder & CEO",
        company="BrightHVAC",
        industry="Home services",
        email="marcus@brighthvac.example",
        fit_reason=(
            "Owner-operator generating inbound web leads but no dedicated SDR; "
            "high risk of slow follow-up losing deals to competitors."
        ),
        fit_score=76,
    ),
]

_SAMPLE_BY_ID = {lead.id: lead for lead in SAMPLE_LEADS}


def list_leads() -> List[Lead]:
    return list(SAMPLE_LEADS)


def get_lead(lead_id: Optional[str]) -> Lead:
    """Return a lead by id, defaulting to the first sample lead."""
    if lead_id and lead_id in _SAMPLE_BY_ID:
        return _SAMPLE_BY_ID[lead_id]
    return SAMPLE_LEADS[0]


def bowtie_configured() -> bool:
    return bool(os.getenv("BOWTIE_API_KEY"))


def fetch_from_bowtie() -> List[Lead]:
    """Placeholder for the real Bowtie / Salesbot.io integration.

    Bowtie exposes qualified, enriched contacts (with fit reasoning) and can
    sync to a CRM. When you have API access, map its contact + qualification
    fields onto :class:`Lead` here. Until then we fall back to the sample set so
    the app always runs.
    """
    # TODO: call the Bowtie export/API with BOWTIE_API_KEY and map results.
    return list_leads()
