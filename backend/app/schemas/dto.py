from dataclasses import dataclass

@dataclass
class VelocityResult:
    user_count: int
    ip_count: int
    user_risk: float
    ip_risk: float
    combined_risk: float
    flagged: bool
    
@dataclass
class GeoLocation:
    ip: str
    lat: float
    lon: float
    city: str
    region: str
    country: str
    country_code: str

@dataclass
class GeoResult:
    current_location: GeoLocation | None
    last_location: GeoLocation | None
    distance_km: float | None
    time_elapsed_seconds: float | None
    required_speed_kmh: float | None
    is_impossible_travel: bool
    risk: float