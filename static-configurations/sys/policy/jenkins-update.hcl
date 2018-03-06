path "sys/auth" {
    capabilities = [
        "read"
    ]
}

path "sys/auth/*" {
    capabilities = [
        "update",
        "create"
    ]
}

path "sys/policy/*" {
    capabilities = [
        "list",
        "read",
        "update",
        "delete",
        "create"
    ]
}

path "sys/mounts" {
    capabilities = [
        "read",
    ]
}

path "sys/mounts/*" {
    capabilities = [
        "list",
        "create",
        "update",
    ]
}

path "sys/*" {
    capabilities = [
        "list"
    ]
}

path "/*" {
    capabilities = [
        "list",
        "read",
        "update",
        "create",
        "delete"
    ]
}