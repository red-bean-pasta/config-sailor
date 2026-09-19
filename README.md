# config-sailor
A lightweight config distribution service written in Python, with server-side document-level JSON patching, designed for simple clients that cannot participate in a handshake-based protocol.


## Why this exists
- Centralized control yet with user-customized output.
- Constrained clients that can only make simple `GET` requests.
- Stealth need for config distribution endpoints.

`config-sailor` therefore provides:
- One base config. Apply patch rules on request.
- Relies solely on standard authentication, headers and query parameters.
- Return `404` on any abnormal requests with timing attacks addressed.

`config-sailor` also treats the host machine as untrusted and stores the base config encrypted without keeping the encryption key on the host. This reduces the impact of data-at-rest compromise.


## How it works
A valid request should bear both correct user credential and decryption key. For every received request, the service will:
- If valid, the base config will be decrypted, patched, and returned;
- If invalid, `404` is returned with an empty body;
- If sent over plain HTTP, exposed valid credentials will be revoked, and then fallback to the invalid path;


## Quickstart

### Installation

1. Debian package (recommended)

It's **recommended** to install the latest `.deb` from GitHub releases, as it installs the systemd service, environment file, and default configuration files as well:
```bash
url=$(wget -qO- https://api.github.com/repos/red-bean-pasta/config-sailor/releases/latest | grep -o 'https://[^\"]*_all\.deb' | head -n1) && file=${url##*/} && wget "$url" && sudo apt install "./$file"
```

2. Using a virtual environment (`pip` or `uv`)

2.1. Clone the repository:
```bash
git clone https://github.com/red-bean-pasta/config-sailor.git
cd config-sailor
```

2.2. Create an isolated system virtual environment and install the project:
Using `uv`:
```bash
sudo uv venv /opt/config-sailor
sudo uv pip install --python /opt/config-sailor .
```
or using standard `python3` / `pip`:
```bash
sudo python3 -m venv /opt/config-sailor
sudo /opt/config-sailor/bin/pip install .
```

2.3. Copy configuration files, templates, and systemd service:

- Copy configuration files and templates:
```bash
sudo mkdir -p /etc/config-sailor/templates
sudo cp data/config-sailor.env data/*.json data/base.enc /etc/config-sailor/
sudo cp -r data/templates/* /etc/config-sailor/templates/
```

- Install systemd service:
```bash
sudo ln -sf /opt/config-sailor/bin/config-sailor /usr/bin/config-sailor
sudo cp data/config-sailor.service /etc/systemd/system/
sudo systemctl daemon-reload
```
The service is not enabled automatically upon installation.


### Setup

1. Check out all the supported commands:
```bash
config-sailor -h
```

2. Encrypt a base config
```bash
config-sailor encrypt base.json /etc/config-sailor/base.enc
```

3. Test building locally 
```bash
config-sailor build --spec-dir /etc/config-sailor/
```

Building locally does not require authentication. Because currently we haven't defined any rules, the base config will be printed as-is. 

4. Add user 
```bash
config-sailor user add someone bearer /etc/config-sailor/
```
This generates a random password and adds it to `/etc/config-sailor/auth.json`. The file and user entry will be automatically generated if missing. 

5. Test serving
```bash
config-sailor serve \
  --spec-dir /etc/config-sailor/ \
  --state-dir /var/lib/config-sailor/ \
  --host 127.0.0.1 \
  --port 9443 \
  -- --workers 4 --log-level info # You can pass extra arguments through to uvicorn after `--`
```

`state-dir` stores runtime-managed files. Currently, it only contains revoked-credentials record. Credentials will be revoked and recorded here when a plaintext HTTP request is received. 


6. Setup reverse proxy
It's recommended to put the service behind a reverse proxy (such as Caddy or Nginx) as the service itself has no rate limiting and is prone to **DoS risk**.

An example Caddyfile is provided at `/etc/config-sailor/templates/Caddyfile`. Apply your specifications, add it to `/etc/caddy/Caddyfile`, and reload Caddy.

> [!IMPORTANT]
> Always remember to redact encryption key from reverse proxy's access logs for query strings.


7. Sending requests
7.1. Authenticate using bearer and header
```bash
curl \
  -H 'Authorization: Bearer username~password' \
  -H 'Encryption-Key: decryption-key' \
  -H 'User-Agent: curl/8.18.0' \
  'https://a.example.com/cfg'
```

7.2. Authenticate using query-string key
```text
https://username:password@a.example.com/cfg?agent=curl&version=8.18.0&key=decryption-key
```

Example 7.2 is **strongly discouraged**. It embeds credentials in URLs and is highly prone to leakage. It should only be used for compatibility reasons with constrained clients.

8. Add rules
`config-sailor` supports **optional** patching rules for user, agent and version. 
All rule files follow the format **[json-config-patch](https://github.com/red-bean-pasta/json-config-patch)**. It's a structure-based and JSON-native patch format with operators like `$modify`, `$select`, and `$insert`. 

On top of json-config-patch, each context defines its own condition matching key: `$user`, `$agent` and `$version`. They are required in each rule and will be matched.

The processing order is first `agent.json`, then `version.json`, and finally `user.json`.

Example base config:
```json
{
  "Umbrella": {
    "artist": "Rihanna",
    "album": "Good Girl Gone Bad",
    "year": 2007
  },
  "Complicated": {
    "artist": "Avril Lavigne",
    "album": "Let Go",
    "year": 2004
  }
}
```

Example user rules (using `$modify`):
```json
{
  "Umbrella": {
    "$modify": {
      "$user": ["Lily"],
      "$assign": {
        "artist": "Rihanna, Jay-Z"
      }
    }
  }
}
```

Example agent rules:
```json
{
  "Umbrella": {
    "$modify": {
      "$agent": "Spotify",
      "$assign": {
        "artist": "Rihanna, Jay-Z"
      }
    }
  }
}
```

Example version rules:
```json
{
  "Umbrella": {
    "$modify": {
      "$version": ">1.0.0, <=3.0.0, !=2.5.9, ~=2.1.0, ==2.2.0",
      "$assign": {
        "artist": "Rihanna, Jay-Z"
      }
    }
  }
}
```
Version matching uses `packaging` library and follows its syntax. It supports `==`, `<`, `>`, `<=`, `>=`, `!=`, `~=`, but no `^=`. Specifiers should be comma separated, and white space is allowed.


9. Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now config-sailor
```

## Additional operators 
On top of [json-config-patch](https://github.com/red-bean-pasta/json-config-patch), `config-sailor` provides an extra **`$replace`** operator for placeholder replacement.

Example:

Base config:
```json
{
  "something": {
    "name": ["placeholder", "ph"],
    "target": "ph2.5",
    "season": "ph"
  }
}
```

Rule:
```json
{
  "something": {
    "$replace": {
      "$user": ["Lily"],
      "$from": ["placeholder", "ph"],
      "$to": "autumn",
      "$recursive": false
    }
  }
}
```
`$from` can be a string or list of strings. `$recursive` is optional and defaults to `false`. 
When `$recursive` is set to `false`, arrays are not processed, even if flat.

Output:
```json
{
  "something": {
    "name": ["placeholder", "ph"],
    "target": "ph2.5",
    "season": "autumn"
  }
}
```


## Caveats
- Limited performance under high throughput as it checks file modification time on every request to reload specs on the fly.
- Transport security attack surface as the request itself carries all the auth credentials, including the decryption key.
