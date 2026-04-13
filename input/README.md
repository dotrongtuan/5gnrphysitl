# Input Assets

This folder contains ready-to-use sample files for PHY file-transfer tests.

Included assets:

- `sample_message.txt`
- `sample_image.png`

CLI examples:

```bash
python main.py --config configs/default.yaml --tx-file input/sample_message.txt --rx-output-dir outputs/rx_files
python main.py --config configs/default.yaml --tx-file input/sample_image.png --rx-output-dir outputs/rx_files
```

GUI examples:

- launch the GUI with `python main.py --config configs/default.yaml --gui`
- set `TX file` to `input/sample_message.txt` or `input/sample_image.png`
- set `RX output` to a writable directory such as `outputs/rx_files`
- press `Run` or `Step Mode`
