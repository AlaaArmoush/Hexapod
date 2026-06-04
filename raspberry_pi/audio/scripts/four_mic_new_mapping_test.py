import time

import numpy as np
import sounddevice as sd


SAMPLE_RATE = 48000
BLOCK_SIZE = 2048
CHANNELS = 4
PRINT_EVERY_SECONDS = 2.0
EPS = 1e-12

# Adjust names only if physical mic placement changes.
# Electrical rule:
# CH0 = GPIO20/pin38, L/R -> GND
# CH1 = GPIO20/pin38, L/R -> 3.3V
# CH2 = GPIO22/pin15, L/R -> GND
# CH3 = GPIO22/pin15, L/R -> 3.3V
MIC_NAMES = [
    "CH0_PIN38_GND",
    "CH1_PIN38_3V3",
    "CH2_PIN15_GND",
    "CH3_PIN15_3V3",
]

DEVICE = 1  # combined overlay capture device: hexapod hw:0,1

energy = np.zeros(CHANNELS, dtype=np.float64)
sample_count = 0
last_print = time.time()


def rms_to_dbfs(rms: float) -> float:
    return 20.0 * np.log10(max(float(rms), EPS))


def make_bar(dbfs: float, min_db: float = -65.0, max_db: float = -25.0, width: int = 32) -> str:
    dbfs = max(min_db, min(max_db, dbfs))
    filled = int((dbfs - min_db) / (max_db - min_db) * width)
    return "#" * filled + "-" * (width - filled)


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

        print()
        print(f"Leading mic: {MIC_NAMES[leader]} | advantage: {advantage_db:.1f} dB")

        order = list(np.argsort(db)[::-1])
        for rank, i in enumerate(order, start=1):
            marker = "<<< LEADER" if i == leader else ""
            print(
                f"  #{rank} CH{i} {MIC_NAMES[i]:14} "
                f"{make_bar(db[i])} "
                f"RMS={rms[i]:.6f} "
                f"dBFS={db[i]:7.1f} "
                f"{marker}"
            )

        print("-" * 100)

        energy[:] = 0.0
        sample_count = 0
        last_print = now


def main():
    print("Available devices:")
    print(sd.query_devices())
    print()
    print("4-mic mapping test. Updates every 2 seconds.")
    print("DEVICE = 1 because combined card capture is hw:0,1")
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
