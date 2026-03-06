-- PlaqueTracker initial schema (Postgres dialect)

-- Users table: stores demographic and baseline oral-health profile
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  full_name TEXT,
  date_of_birth DATE,
  age INTEGER,
  gender TEXT,
  braces_status BOOLEAN DEFAULT FALSE,
  cavity_history TEXT,
  dental_history TEXT,
  brushing_frequency INT,
  flossing_frequency INT,
  dietary_patterns JSONB,
  baseline_pH_min NUMERIC(3,2),
  baseline_pH_max NUMERIC(3,2),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Devices
CREATE TABLE devices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  device_model TEXT,
  firmware_version TEXT,
  calibration_state JSONB,
  registered_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Sensor readings (direct electrochemical measurements)
CREATE TABLE sensor_readings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  device_id UUID REFERENCES devices(id),
  recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
  pH_value NUMERIC(3,2),
  temperature NUMERIC(5,2),
  source_type TEXT DEFAULT 'sensor', -- sensor or image
  confidence NUMERIC(4,3),
  battery_level SMALLINT,
  raw_packet JSONB,
  processed BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
CREATE INDEX ON sensor_readings (user_id);
CREATE INDEX ON sensor_readings (recorded_at);

-- Hydrogel image scans and metadata
CREATE TABLE hydrogel_scans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  image_s3_key TEXT,
  recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
  estimated_pH NUMERIC(3,2),
  confidence NUMERIC(4,3),
  calibration_state JSONB,
  device_id UUID REFERENCES devices(id),
  lighting_metadata JSONB,
  processing_metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
CREATE INDEX ON hydrogel_scans (user_id);
CREATE INDEX ON hydrogel_scans (recorded_at);

-- Analytics results: risk indices, cavity predictions, feature payloads
CREATE TABLE analytics_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  window_start TIMESTAMP WITH TIME ZONE,
  window_end TIMESTAMP WITH TIME ZONE,
  plaque_risk_index NUMERIC(5,3),
  cavity_probability NUMERIC(5,4),
  features JSONB,
  model_version TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
CREATE INDEX ON analytics_results (user_id);

-- Streaks and rewards
CREATE TABLE streaks_rewards (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  current_streak INT DEFAULT 0,
  best_streak INT DEFAULT 0,
  xp BIGINT DEFAULT 0,
  badges JSONB DEFAULT '[]'::JSONB,
  last_awarded TIMESTAMP WITH TIME ZONE
);

-- Audit / event log
CREATE TABLE event_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  event_type TEXT,
  event_payload JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Useful constraints/indexes
CREATE INDEX ON event_logs (user_id);
