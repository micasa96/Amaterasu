package config

type Registration struct {
	AppID   int      `json:"app_id"`
	AppHash string   `json:"app_hash"`
	Tokens  []string `json:"tokens"`
	Stream  *Stream  `json:"stream,omitempty"`
}

type Stream struct {
	Secret     string `json:"secret"`
	MongoURI   string `json:"mongo_uri"`
	Partition  string `json:"partition"`
	PythonPort int    `json:"python_port"`
	RclonePort int    `json:"rclone_port"`
}
