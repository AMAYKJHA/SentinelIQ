from dataclasses import dataclass

@dataclass
class VelocityResult:
    user_count: int
    ip_count: int
    user_risk: float
    ip_risk: float
    combined_risk: float
    flagged: bool