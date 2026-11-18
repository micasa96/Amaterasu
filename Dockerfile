ARG BASE_IMAGE=docker.io/nbots/amaterasu:v1

# ── Web UI build stage ────────────────────────────────────────────────
# The web pages are Svelte apps sharing one design system (web/ui). This
# stage builds them to web/static/dist; only the built files reach the
# runtime image, so the final image carries no Node toolchain.
FROM docker.io/library/node:24-bookworm-slim AS web-ui
WORKDIR /src/web/ui
COPY web/ui/package.json web/ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ui/ ./
# The player page imports the vanilla runtime from web/static/js (kept there
# for its tests), so it must exist at /src/web/static/js during the build.
COPY web/static/js/ /src/web/static/js/
RUN npm run build

FROM ${BASE_IMAGE}

ENV LANG=C.UTF-8 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Dhaka \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/amaterasuvenv \
    PATH="/amaterasuvenv/bin:${PATH}"

WORKDIR /usr/src/app

# Keep the media and archive tools required by the app in the runtime image
# instead of relying on the currently published base-image contents.
RUN apt-get update \
    && apt-get install -y --no-install-recommends mkvtoolnix p7zip-full unzip \
    && rm -rf /var/lib/apt/lists/* \
    && command -v mkvmerge \
    && command -v mkvextract \
    && command -v 7z \
    && 7z i >/dev/null

# Install Deno — required by yt-dlp for solving YouTube's n-sig challenge.
# Without a JS runtime, yt-dlp fails with "n challenge solving failed" and
# "The page needs to be reloaded", making all video formats unavailable.
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && deno --version

# Create the virtual environment WITH --system-site-packages.
# This is CRITICAL: the Mega SDK Python bindings are installed in system
# Python's site-packages (by Dockerfile.base Block 7). Without this flag,
# the venv is isolated and can't import 'mega.MegaApi' → Mega download/upload
# fails with "Mega SDK Python bindings are not installed in this image".
# The Rust extension from Dockerfile.base is inherited here as well.
RUN python3 -m venv --system-site-packages /amaterasuvenv

# Install uv into the venv for fast package installation
# (sabnzbdplus is installed via apt in the base image, not pip — it's not on PyPI)
RUN /amaterasuvenv/bin/pip install --no-cache-dir uv

# Install python dependencies using uv
COPY requirements.txt .
RUN /amaterasuvenv/bin/uv pip install --python /amaterasuvenv/bin/python --no-cache-dir -r requirements.txt \
    && /amaterasuvenv/bin/python -c "from importlib.metadata import version; import pyrogram, warpcrypto; from pyrogram.crypto import aes; assert pyrogram.__version__ == '3.1.7', pyrogram.__version__; assert version('warpcrypto') == '2.0.8', version('warpcrypto'); assert getattr(aes, 'warpcrypto', None) is warpcrypto, 'WarpCrypto is not WZGram active crypto backend'; print('Verified WZGram 3.1.7 with active WarpCrypto 2.0.8 backend')"

# Copy all the project files
COPY . .
# Keep built assets outside the Compose checkout mount at /usr/src/app.
ENV AMATERASU_UI_DIST=/opt/amaterasu-ui
COPY --from=web-ui /src/web/static/dist ${AMATERASU_UI_DIST}

# Setup permissions and convert Windows line endings to Unix just in case
RUN sed -i 's/\r$//' *.sh \
    && chmod +x start.sh \
    && /amaterasuvenv/bin/python -c "from terabox import TeraboxClient; import aioterabox; print('Verified Amaterasu TeraBox SDK')"

# Start the bot
CMD ["bash", "start.sh"]
