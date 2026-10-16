package ssra.policy_gate

import rego.v1

default decision := "DENY"

# Tier T4 is always human-only: explain process and hand off
decision := "HANDOFF" if {
    input.tier == "T4"
}

decision := "HANDOFF" if {
    input.intent == "human_handoff"
}

# Tier T0 public intents are allowed for all auth levels unless rate-limited or unsafe
decision := "ALLOW" if {
    input.tier == "T0"
    input.intent != "human_handoff"
    not input.rate_limited
}

# Tier T1 and T2 require at least T1_TIN_BOUND authentication
decision := "ALLOW" if {
    input.tier in {"T1", "T2"}
    input.auth_level in {"T1_TIN_BOUND", "T3_STEP_UP", "STAFF_PASSKEY"}
    input.subject_ref != null
    not input.rate_limited
}

decision := "STEP_UP" if {
    input.tier in {"T1", "T2"}
    not input.auth_level in {"T1_TIN_BOUND", "T3_STEP_UP", "STAFF_PASSKEY"}
}

# Tier T3 requires fresh step-up authentication
decision := "ALLOW" if {
    input.tier == "T3"
    input.auth_level == "T3_STEP_UP"
    input.subject_ref != null
    not input.rate_limited
}

decision := "STEP_UP" if {
    input.tier == "T3"
    input.auth_level != "T3_STEP_UP"
}
