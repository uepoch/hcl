path "services/accounts/{{identity.entity.name}}" {
    capabilities = ["read", "list"]
}

path "services/secrets/{{identity.entity.name}}/*" {
    capabilities = ["read", "list"]
}