path "sys/auth" {
    capabilities = [
        "read",
        "list"
    ]
}

path "sys/plugins/*" {
    capabilities = [
        "read",
        "list"
    ]
}

path "sys/auth/*" {
    capabilities = [
        "read",
        "update",
        "create",
        "list"
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
        "list"
    ]
}

path "sys/mounts/*" {
    capabilities = [
        "read",
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
