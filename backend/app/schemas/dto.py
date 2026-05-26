from dataclasses import dataclass

@dataclass
class VelocityResult:
    user_count: int
    ip_count: int
    user_risk: float
    ip_risk: float
    flagged: bool
    
@dataclass
class GeoLocation:
    ip: str
    lat: float
    lon: float
    city: str
    country: str
    asn: str

@dataclass
class GeoResult:
    current_location: GeoLocation | None
    last_location: GeoLocation | None
    distance_km: float | None
    time_elapsed_seconds: float | None
    required_speed_kmh: float | None
    is_impossible_travel: bool
    risk: float

@dataclass
class EmailSchema:
    to_email: str
    subject: str
    template_name: str
    template_params: dict