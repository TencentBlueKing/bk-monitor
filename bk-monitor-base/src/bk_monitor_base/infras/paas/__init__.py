import os

IS_PAAS3 = os.environ.get("BKPAAS_MAJOR_VERSION", "") == "3"
