"""Testing utilities for DHMC attack simulation.

These functions are for testing and demonstration ONLY.
They should never be imported in production code.
"""


def simulate_post_execution_tamper(dhmc, target_uri: str, tampered_payload):
    """Simulate an adversary modifying a stored CAS payload after execution.

    WARNING: This is an ATTACK SIMULATION function for testing only.
    """
    if target_uri in dhmc.cas_store:
        dhmc.cas_store[target_uri] = tampered_payload
        print(f"  [ATTACK-SIM] CAS entry tampered: {target_uri[:60]}...")
