# NVIDIA extensions to Nautobot API Package

## LPU C2C REST API

The normalized LPU C2C resources are available below `/api/plugins/nvdatamodels/`:

| Resource | Path | Access |
| :------- | :--- | :----- |
| Domains | `lpu-c2c-domains/` | CRUD, plus projection and controlled rack-position actions |
| Rack positions | `lpu-c2c-rack-positions/` | Read-only; use the Domain action for changes |
| DeviceType compatibility | `lpu-c2c-device-type-compatibilities/` | CRUD |
| Endpoint configuration | `lpu-c2c-endpoint-configurations/` | Lifecycle-validated CRUD for exclusions and overrides |

### Domain topology projection

Read the canonical live projection with:

```http
GET /api/plugins/nvdatamodels/lpu-c2c-domains/<domain-uuid>/topology-projection/
```

A ready response uses lowercase REST state and severity values. Rack positions are ordered and include vacancies (`rack: null`); endpoints are ordered by rack ordinal, rack-local coordinate, and Device UUID. For LP30 coordinates, `rack_ordinal` is zero-based and `tray_slot` is a one-based, rack-wide position numbered 1 through 16 from bottom to top.

```json
{
  "domain": {
    "object_type": "nautobot_nvdatamodels.lpuc2cdomain",
    "id": "11111111-1111-1111-1111-111111111111",
    "display": "LP30 Fabric 1"
  },
  "state": "ready",
  "projection": {
    "rack_positions": [
      {
        "position": {
          "object_type": "nautobot_nvdatamodels.lpuc2cdomainrackposition",
          "id": "22222222-2222-2222-2222-222222222222",
          "display": "LP30 Fabric 1 position 0"
        },
        "rack": {
          "object_type": "dcim.rack",
          "id": "33333333-3333-3333-3333-333333333333",
          "display": "Rack 01"
        }
      }
    ],
    "endpoints": [
      {
        "device": {
          "object_type": "dcim.device",
          "id": "44444444-4444-4444-4444-444444444444",
          "display": "LPU Tray 01"
        },
        "domain": {
          "object_type": "nautobot_nvdatamodels.lpuc2cdomain",
          "id": "11111111-1111-1111-1111-111111111111",
          "display": "LP30 Fabric 1"
        },
        "coordinate": {
          "rack_ordinal": 0,
          "tray_slot": 1
        }
      }
    ]
  },
  "diagnostics": []
}
```

An expected invalid topology is still a successful read: it returns HTTP 200, `state: "invalid"`, `projection: null`, and Domain-level diagnostics. An invalid topology exposes no usable subset of coordinates.

```http
HTTP/1.1 200 OK
```

```json
{
  "domain": {
    "object_type": "nautobot_nvdatamodels.lpuc2cdomain",
    "id": "11111111-1111-1111-1111-111111111111",
    "display": "LP30 Fabric 1"
  },
  "state": "invalid",
  "projection": null,
  "diagnostics": [
    {
      "severity": "error",
      "code": "INCOMPATIBLE_DEVICE_TYPE",
      "message": "Installed LPU tray device type is not compatible with the domain topology.",
      "affected_objects": [
        {
          "object_type": "dcim.device",
          "id": "44444444-4444-4444-4444-444444444444",
          "display": "LPU Tray 01"
        }
      ]
    }
  ]
}
```

Projection authorization is all-or-nothing: a caller that cannot view every required source object receives HTTP 403 without partial topology data. A missing Domain returns HTTP 404.

### Controlled rack-position changes

Use the lifecycle-aware Domain action instead of writing rack-position rows directly:

```http
POST /api/plugins/nvdatamodels/lpu-c2c-domains/<domain-uuid>/rack-position-operation/
Content-Type: application/json
```

For example, filling an existing vacancy is:

```json
{
  "operation": "fill",
  "ordinal": 2,
  "rack": "33333333-3333-3333-3333-333333333333"
}
```

Every payload includes an `operation` value. The remaining accepted fields are operation-specific; fields not listed for that operation are rejected.

| Operation | Required fields | Optional fields | Effect |
| :-------- | :-------------- | :-------------- | :----- |
| `append` | None | `rack` | Add the next ordinal, vacant when `rack` is omitted or null. |
| `fill` | `ordinal`, `rack` | None | Occupy an existing vacant ordinal. |
| `vacate` | `ordinal` | None | Clear the Rack while retaining the ordinal. |
| `remove_and_compact` | `ordinal`, `confirmed: true` | None | Delete the position and decrement every later ordinal. |
| `insert` | `ordinal`, `confirmed: true` | `rack` | Insert a position and increment ordinals at or above it; omit or null `rack` for a vacancy. |
| `reorder` | `ordering`, `confirmed: true` | None | Apply `ordering`, which must contain every current ordinal exactly once. |

`remove_and_compact`, `insert`, and `reorder` require explicit confirmation. Physical-topology changes are accepted only while the Domain is Planned or in Maintenance; an Active Domain must enter Maintenance first.

## LPU C2C GraphQL API

The public camel-case list roots and their tested filter signatures are:

```graphql
lpuC2cDomains(id: [String])
devices(location: [String])
```

The schema also exposes the camel-case singular Domain root `lpuC2cDomain`. The examples below use the list roots because Nautobot filters accept lists of string UUIDs. For LP30 coordinates, `rackOrdinal` is zero-based and `traySlot` is a one-based, rack-wide position numbered 1 through 16 from bottom to top.

### Query from a Domain

```graphql
query LpuC2cDomainProjection($id: [String]) {
  lpuC2cDomains(id: $id) {
    id
    name
    projectionState
    diagnostics {
      severity
      code
      message
      affectedObjects {
        objectType
        objectId
      }
    }
    endpoints {
      device { id name }
      domain { id }
      coordinate {
        rackOrdinal
        traySlot
      }
    }
  }
}
```

```json
{
  "id": ["11111111-1111-1111-1111-111111111111"]
}
```

GraphQL enum responses are uppercase even though the REST values are lowercase. For an invalid Domain, candidate endpoints remain discoverable but their coordinates are null:

```json
{
  "data": {
    "lpuC2cDomains": [
      {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "LP30 Fabric 1",
        "projectionState": "INVALID",
        "diagnostics": [
          {
            "severity": "ERROR",
            "code": "INCOMPATIBLE_DEVICE_TYPE",
            "message": "Installed LPU tray device type is not compatible with the domain topology.",
            "affectedObjects": [
              {
                "objectType": "dcim.device",
                "objectId": "44444444-4444-4444-4444-444444444444"
              }
            ]
          }
        ],
        "endpoints": [
          {
            "device": {
              "id": "44444444-4444-4444-4444-444444444444",
              "name": "LPU Tray 01"
            },
            "domain": {"id": "11111111-1111-1111-1111-111111111111"},
            "coordinate": null
          }
        ]
      }
    ]
  }
}
```

`projectionState` returns `READY` or `INVALID`; diagnostic severity returns `ERROR` or `WARNING`. Diagnostics exist only on `LPUC2CDomainType`, not on `LPUC2CEndpointProjectionType`.

### Query from a Device

Core Device objects expose the derived `lpuC2c` field:

```graphql
query DeviceLpuC2c($location: [String]) {
  devices(location: $location) {
    id
    name
    lpuC2c {
      device { id name }
      domain {
        id
        name
        topology
        projectionState
        diagnostics { code severity }
      }
      coordinate {
        rackOrdinal
        traySlot
      }
    }
  }
}
```

`Device.lpuC2c` is null when the Device has no candidate membership, is explicitly excluded, or belongs to a candidate Domain the caller cannot view. An invalid candidate still returns the shared endpoint projection with `coordinate: null`; follow `lpuC2c.domain` for its projection state and diagnostics.

When a Domain projection source is not visible, the Domain's `projectionState`, `diagnostics`, and `endpoints` fields return null with GraphQL field errors instead of returning a filtered topology.

## Python API reference

::: nautobot_nvdatamodels.api
    options:
        show_submodules: True
