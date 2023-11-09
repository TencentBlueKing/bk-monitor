def safe_int(int_str, dft=0):
    try:
        int_val = int(int_str)
    except Exception:
        try:
            int_val = int(float(int_str))
        except Exception:
            int_val = dft
    return int_val
