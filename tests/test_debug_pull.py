"""Debug test to see what's happening during a pull."""

import time
from api.services.dyno_simulator import (
    DynoSimulator,
    SimulatorConfig,
    EngineProfile,
    SimState,
)


def test_debug_pull():
    """Debug a pull to see RPM progression."""
    sim = DynoSimulator()
    sim.start()
    time.sleep(0.2)
    
    print(f"\nInitial state: {sim.state}")
    print(f"Initial RPM: {sim.physics.rpm}")
    print(f"Initial TPS: {sim.physics.tps_actual}")
    
    sim.trigger_pull()
    
    print(f"\nAfter trigger:")
    print(f"State: {sim.state}")
    print(f"TPS target: {sim.physics.tps_target}")
    
    # Monitor for 10 seconds
    for i in range(100):
        time.sleep(0.1)
        if i % 10 == 0:  # Every second
            print(f"\nT={i/10:.1f}s: RPM={sim.physics.rpm:.0f}, TPS={sim.physics.tps_actual:.1f}%, State={sim.state.value}")
            print(f"  Angular vel={sim.physics.angular_velocity:.2f} rad/s, Accel={sim.physics.angular_acceleration:.2f} rad/s²")
        
        if sim.state == SimState.IDLE:
            print(f"\nReturned to IDLE at T={i/10:.1f}s")
            break
    
    print(f"\nFinal state: {sim.state}")
    print(f"Final RPM: {sim.physics.rpm}")
    
    pull_data = sim.get_pull_data()
    if pull_data:
        rpms = [d["Engine RPM"] for d in pull_data]
        print(f"\nPull data: {len(pull_data)} samples")
        print(f"RPM range: {min(rpms):.0f} - {max(rpms):.0f}")
    
    sim.stop()


if __name__ == "__main__":
    test_debug_pull()

