# config-sailor
A lightweight config distribution service written in Python, with server-side document-level JSON patching.

`config-sailor` supports two main workflows:
- **build**: decrypt a base config and apply optional rules locally
- **serve**: expose a stealthy config endpoint over HTTP(S) that authenticates the caller, decrypts the base config, applies matching patches, and returns the final JSON

It is designed for simple clients that can only do a plain `GET` request and cannot participate in a handshake-based protocol.

---

## Why this exists
### Centralized control with customized output
There are often cases where one wish to manage config file centrally to reduce maintenance burden, while still delivering client-specific customization at request time. 
`config-sailor` supports this by storing an encrypted base config and applying patch rules when a request is received. 

### Constrained clients
Many clients can only make simple `GET` requests but do not support handshake-based protocol. This is especially common for third-party or mobile clients.
`config-sailor` is designed with this limitation in mind and relies only on standard authentication, headers, and query parameters.

### Stealth requirements
A config distribution endpoint should avoid drawing unnecessary attention.
`config-sailor` therefore returns `404` with an empty body for any invalid request. This helps obscure the presence of the service.
`config-sailor` is also designed with timing attacks in mind. Authentication and decryption are handled to keep request processing on a nearly consistent timing path.

### Encrypted storage
The host machine may not always be fully trusted.
`config-sailor` stores the base config in encrypted form without keeping the encryption key on the host. The key is expected to be supplied by the request. While not an ideal design, this reduces the impact of data-at-rest compromise.

---

## Features
- **Encrypted base config at rest**
- **Rule-based patching** by:
  - user
  - client version
  - client agent
- **Simple GET-based delivery**
- **Basic and Bearer authentication**
- **Stealth-oriented failure behavior**
  - invalid requests return `404` with no body
  - authentication is designed to avoid obvious timing differences
- **Automatic reload-on-change**
  - spec files are checked for modification on each request
- **CLI utilities**
  - generate secrets
  - hash credentials
  - encrypt config
  - edit encrypted config
  - build config locally
  - serve config over HTTP(S)

---

## How it works
At a high level:
1. Encrypt and store the base config as `base.json.enc`
2. Define optional patch files for
	- `user`
	- `agent`
	- `version`
3. If using `serve`, define authentication rules in `auth_rules.json`
4.  A client sends:
	- authentication credentials
	- decryption key
	- optional agent and version information
5. Service validates the credentials and decryption key
6. If the request is invalid, it returns `404` with empty body
7. If the request was sent over plain HTTP, it revokes exposed valid credentials and returns `404`
8. If the request is valid, it decrypts the base config
9. Service selects all rules that match the request context
10. It applies patches to the decrypted config
11. It returns the final JSON config

---

## Spec directory layout
A spec directory always contains the encrypted base config, and may contain zero or more rule files.
**Required for `build`**
`base.json.enc`

**Required for `serve`**
`base.json.enc`
`auth_rules.json`

**Optional**
`user_rules.json`
`agent_rules.json`
`version_rules.json`

---

### Auth rules
#### `auth_rules.json`
Credentials must be stored as hashes, not plaintext.
**Example**:
```js
{
  "user1": {
    "bearer": "$argon2id$v=19$m=65536,t=3,p=3$F7AC...",
    "basic": "$argon2id$v=19$m=65536,t=3,p=3$WvA2..."
  },
  "user2": {
    "bearer": "$argon2id$v=19$m=65536,t=3,p=3$zGrq..."
  },
  ...
}
```

---

### Patch rules
Each context requires its own rule file.

All rule files follow the format **[json-config-patch](https://github.com/red-bean-pasta/json-config-patch)**, a structure-based and JSON-native patch specification with handy JSON transform operators like `$modify`, `$filter`, `$select` and `$insert`. 

On top of json-config-patch, each context defines its own selector key:
* `user_rules.json`: `$user`
* `agent_rules.json`: `$agent`
* `version_rules.json`: `$version`

The selector key must be present in each rule. A rule is selected only if its selector matches the current request context. 

Execution order: `agent_rules.json > version_rules.json > user_rules.json`

**Examples**:
`user_rules.json`
```js
{
	"field 1": {
		"$modify": {
			"$user": ["shapeshifter", "hype-boy"],
			"$assign": {
				"field 1.1": "value"
			},
			...
		},
		...
	},
	...
}
```

`agent_rules.json`
```js
{
  "field 1": {
    "$modify": {
      "$agent": ["BirdsOfAFeather", "LOML"],
      "$assign": {
        "field 1.1": "value"
      },
	  ...
    },
	...
  },
  ...
}
```


### `version_rules.json`
```js
{
	"field 1": {
		"$modify": {
			"$version": ">1.0.0, <=3.0.0, !=2.5.9, ~=2.1.0, ==2.2.0",
			"$assign": {
				"field 1.1": "value"
			},
			...
		},
		...
	},
	...
}
```

> Version matching uses Python’s `packaging` library specifier syntax.
> It supports `==`, `<`, `>`, `<=`, `>=`, `!=`, `~=`, but no `^=`.
> Specifiers should be comma separated. White space is allowed.
> Contradictory ranges like `<0.9, >1.0` do not throw an error, but will never match.
> Example: `>1.0.0, <= 3.0.0`

---

## State directory
`state-dir` stores runtime-managed files. 

Currently this includes the revoked-credentials record.
Example:
```text
this_was_a_password
this_was_another_password
```
This is intentionally simple and append-friendly.

---

## Request model
The service is intended for very simple clients, so everything can be sent through standard HTTP headers or query parameters.
### Authentication
Two authentication methods are supported:
- **Bearer**
- **Basic**

A user may have either or both methods configured.

> Authentication secrets in the URL path or query string are intentionally not accepted. They are more likely to leak through logs, caches, and intermediaries.

#### Bearer format
Bearer credentials are structured as:
```text
Authorization: Bearer <user>~<credential>
```

#### Basic format
Basic auth uses the standard `user:password` form.
Example:
```http
Authorization: Basic base64(user:password)
```

#### Authentication Logic
- Either Basic or Bearer is sufficient if both are configured for the same user
- If both are provided:
	- both must be valid
	- the usernames must match
- If any provided method fails validation, the request is rejected
- If all methods are absent, the request is rejected

### Decryption key
The request must also provide the key used to decrypt the base config.
It can be sent by:
* header: `Encryption-Key`
* query string: `?key=...`

**Example**:
```http
Encryption-Key: the-shared-decryption-key
```
or
```text
/cfg?key=the-shared-decryption-key
```

### Patching context
Rule matching uses:
* From authentication identity
	* **user** 
* From "User-Agent" header or query parameters:
	* **version** 
	* **agent**

**Examples**:
```http
User-Agent: curl/8.18.0
```
or 
```text
/cfg?agent=curl&version=8.18.0
```

- `user` cannot be specified by query parameter
- Query parameters take precedence over header-derived values

---

## Failure behavior
This service is intentionally opinionated. 

### Stealth
For invalid requests such as wrong path, invalid auth or incorrect decryption key, the service responds with `HTTP 404` and an **empty body**. This is deliberate. A config distribution endpoint should remain low-profile without revealing whether a real service exists. 
The implementation also aims to keep authentication and decryption checks on a nearly consistent timing path. This reduces timing-based information leakage and makes timing attacks harder.
  
### Plain HTTP exposure
If a request is sent over plain HTTP, it will be rejected with `HTTP 404` and an empty body. 
The request is still validated but any valid credentials will be revoked.
The decryption key cannot be revoked without breaking all clients, so key exposure is only logged.
`unsafe mode` can be enabled to disable revocation. This is discouraged outside trusted internal environments.

---

## CLI
Available commands:
* `generate`: Generate random URL-safe secret. Useful for randomly generating password or bearer token
* `hash`: Hash authentication credentials before storing in `auth_rules.json`
* `encrypt`: Generate a random encryption key and encrypt a config file
* `edit`: Decrypt an encrypted config file, edit it, then re-encrypt it
* `build`: Generate a patched config from a spec directory. No authentication needed. `user`, `agent` and `version` are supplied via CLI arguments
* `serve`: Start a config patching service over HTTP

---

## Installation
### Debian package (recommended)
Download the latest `.deb` from GitHub Releases and install it locally:
```bash
url=$(wget -qO- https://api.github.com/repos/red-bean-pasta/config-sailor/releases/latest | grep -o 'https://[^"]*_all\.deb' | head -n1) && file=${url##*/} && wget "$url" && sudo apt install "./$file"
```
This method is recommended on Debian-based systems as it also installs the systemd service, environment file, and default configuration files.

### Install from GitHub with `pip`
```bash
pip install git+https://github.com/red-bean-pasta/config-sailor.git
```

### Install from GitHub with `uv`
```bash
uv tool install git+https://github.com/red-bean-pasta/config-sailor.git
```

---

## Quickstart
### 1. Encrypt a base config
```bash
config-sailor encrypt ./base.json ./spec/base.json.enc
```
### 2. Generate a credential or token
```bash
config-sailor generate
```
### 3. Hash credentials for auth rules
```bash
config-sailor hash [my-password]
config-sailor hash [my-bearer-secret]
```
Put the generated hashes into `auth_rules.json`.
### 4. Build locally
```bash
config-sailor build \
  --spec-dir ./spec \
  --user someone \
  --agent some-agent \
  --version 1.2.3
```
### 5. Serve
```bash
config-sailor serve \
  --spec-dir ./spec \
  --state-dir ./state \
  --host 127.0.0.1 \
  --port 9443
```
Pass extra arguments through to uvicorn after `--`:
```bash
config-sailor serve \
  --spec-dir ./spec \
  --state-dir ./state \
  --port 8000 \
  -- --workers 4 --log-level trace
```

See more about each command, use:
```bash
config-sailor -h
```

---

## Recommended deployment posture
For production-like environments:
* run behind reverse proxy like Caddy or Nginx:
	* add rate limiting
	* redact access log for query strings
	* terminate TLS 
* trust forwarded headers only from known proxy IPs
* use Bearer auth where clients support it
* pass the decryption key in a header, not a query string
* keep `unsafe-mode` off

Avoid:
* exposing the service directly to the internet without a reverse proxy
* using plain HTTP except in trusted development
* putting secrets in URLs as logs or upstream tooling may capture them

---

## Example request patterns
### Bearer + header key
```bash
curl \
  -H 'Authorization: Bearer someone~some-bearer-secret' \
  -H 'Encryption-Key: some-decryption-key' \
  'https://some.example.com/cfg?agent=desktop'
```

### URL with query-string key for minimal clients 
```text
https://someone:some-password@some.example.com/cfg?key=some-decryption-key
```
This is **strongly discouraged** in production and is only supported for compatibility with constrained clients, since credentials embedded in URLs are highly prone to leakage.

---

## Operational caveats
### Performance
This project may not perform well under high throughput:
- The service is written in Python and may not perform well under high throughput.
- The service checks file modification times on every request to reload specs on the fly, which adds filesystem I/O overhead to every request.

### No built-in rate limiting
There is currently no internal rate limiting. Direct exposure to the public internet increases DoS risk. Use firewall rules or reverse proxy controls.

### Transport security matters
Even though the base config is encrypted at rest, the request itself can carry auth credentials, the decryption key and version and agent metadata. 

### User management 
Users and credential hashes are stored in JSON files. User management is manual. It does not scale well when the number of users grows large.
