from pydantic import BaseModel, EmailStr

class LoginCredentials(BaseModel):
    email: EmailStr
    password: str
    
class DeviceSpec(BaseModel):
    device_fingerprint: str
    hardware_concurrency: int
    device_memory: int
    screen_width: int
    screen_height: int
    pixel_ratio: int
    is_touch: bool
    platform: int
    user_agent: str
    color_depth: str
    plugins_hash: str
    canvas_hash: str
    webgl_renderer: str
    
class NetworkContext(BaseModel):
    timezone: str
    language: str
    languages: list[str]
    connection_type: str
    webrtc_local_ip: str | None
    do_not_track: str | None
    
class BehavioralSignals(BaseModel):
    form_time_ms: int
    password_pasted: bool
    username_pasted: bool
    avg_dwell_time_ms: float
    avg_flight_time_ms: float
    keystroke_variance: float
    typo_count: int
    mouse_event_count: int
    mouse_linearity: float
    mouse_avg_speed: float
    used_tab_to_navigate: bool
  
class SessionMetadata(BaseModel):
    session_id: str
    referrer: str | None
    cookies_enabled: bool
    headless_signals: str
    webdriver: bool
    chrome_headless: bool
    no_plugins: bool
    
class LoginRequest(BaseModel):
    credentials: LoginCredentials
    device_spec: DeviceSpec
    network_context: NetworkContext
    behavioral_signals: BehavioralSignals   
    session_metadata: SessionMetadata