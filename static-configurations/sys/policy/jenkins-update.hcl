path "auth/*" {
    capabilities = [
        "list"
    ]
}

path "sys/policy/*" {
    capabilities = [
        "list",
        "read",
    ]
}

path "sys/mounts" {
    capabilities = [
        "list"
    ]
}

path "/sys/*" {
    capabilities = [
        "deny"
    ]
}

path "/*" {
    capabilities = [
        "update",
        "create",
        "delete"
    ]
}