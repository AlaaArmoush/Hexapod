import time
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 48000
BLOCK_SIZE = 2048
CHANNELS = 4
PRINT_EVERY_SECONDS = 2.0
EPS = 1e-12

# Rename these after final physical placement.
MIC_NAMES = [
    "CH0_PAIR1_LEFT",
    "CH1_PAIR1_RIGHT",
    "CH2_PAIR2_LEFT",
    "CH3_PAIR2_RIGHT",
]

# None usually works if hexapod-4mic is the default input.
# If not, set this to the sounddevice input index for hexapod-4mic.
DEVICE = None

energy = np.zeros(CHANNELS, dtype=np.float64)
sample_count = 0
last_print = time.time()


def rms_to_dbfs(rms: float) -> float:
    return 20.0 * np.log10(max(float(rms), EPS))


def make_bar(dbfs: float, min_db: float = -70.0, max_db: float = -20.0, width: int = 24) -> str:
    dbfs = max(min_db, min(max_db, dbfs))
    filled = int((dbfs - min_db) / (max_db - min_db) * width)
    return "█" * filled + "-" * (width - filled)


def callback(indata, frames, time_info, status):
    global energy, sample_count, last_print

    if status:
        print(f"[Audio status] {status}")

    if indata.shape[1] < CHANNELS:
        print(f"ERROR: expected {CHANNELS} channels, got {indata.shape[1]}")
        return

    x = indata[:, :CHANNELS].astype(np.float64)

    energy += np.sum(x * x, axis=0)
    sample_count += x.shape[0]

    now = time.time()
    if now - last_print >= PRINT_EVERY_SECONDS:
        rms = np.sqrt(energy / max(sample_count, 1))
        db = np.array([rms_to_dbfs(v) for v in rms])

        leader = int(np.argmax(db))
        sorted_db = np.sort(db)
        advantage_db = sorted_db[-1] - sorted_db[-2]

        if advantage_db < 3.0:
            direction = "UNCERTAIN"
        else:
            direction = MIC_NAMES[leader]

        print()
        print(f"Leading direction: {direction} | lead advantage: {advantage_db:.1f} dB")

        for i in range(CHANNELS):
            marker = "<-- LEADER" if i == leader and advantage_db >= 3.0 else ""
            print(
                f"  CH{i} {MIC_NAMES[i]:18} "
                f"RMS={rms[i]:.6f}  "
                f"dBFS={db[i]:7.1f}  "
                f"{make_bar(db[i])} {marker}"
            )

        print("-" * 90)

        energy[:] = 0.0
        sample_count = 0
        last_print = now


def main():
    print("Available devices:")
    print(sd.query_devices())
    print()
    print("Listening with 4 mics. Updates every 2 seconds. Ctrl+C to stop.")
    print("Expected mapping:")
    print("  CH0 = pair 1 left  / GPIO20 left slot")
    print("  CH1 = pair 1 right / GPIO20 right slot")
    print("  CH2 = pair 2 left  / GPIO22 left slot")
    print("  CH3 = pair 2 right / GPIO22 right slot")
    print()

    with sd.InputStream(
        device=DEVICE,
        channels=CHANNELS,
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        dtype="float32",
        callback=callback,
    ):
        while True:
            sd.sleep(1000)


if __name__ == "__main__":
    main()