path "sys/auth" {
    capabilities = [
        "read",
        "list",
        "sudo"
    ]
}

path "sys/plugins/*" {
    capabilities = [
        "read",
        "list",
        "sudo"
    ]
}

path "sys/auth/*" {
    capabilities = [
        "read",
        "update",
        "create",
        "list",
        "sudo"
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
