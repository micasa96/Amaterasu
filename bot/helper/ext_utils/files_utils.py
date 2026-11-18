from aioshutil import rmtree as aiormtree, move
from asyncio import create_subprocess_exec, wait_for
from asyncio.subprocess import PIPE
from psutil import disk_usage
from os import fsync, link, path as ospath, readlink, walk
from pathlib import Path
from re import I, escape, findall as re_findall, search as re_search, split as re_split
from shutil import copyfileobj
from tempfile import TemporaryDirectory

from aiofiles.os import (
    listdir,
    remove,
    rmdir,
    symlink,
    makedirs as aiomakedirs,
    path as aiopath,
    readlink as aioreadlink,
)
from magic import Magic

from ... import DOWNLOAD_DIR, LOGGER
from ...core.torrent_manager import TorrentManager
from .bot_utils import cmd_exec, sync_to_async
from .exceptions import NotSupportedExtractionArchive
from .rust_bridge import rust_core

ARCH_EXT = [
    ".tar.bz2",
    ".tar.gz",
    ".bz2",
    ".gz",
    ".tar.xz",
    ".tar",
    ".tbz2",
    ".tgz",
    ".lzma2",
    ".zip",
    ".7z",
    ".z",
    ".rar",
    ".iso",
    ".wim",
    ".cab",
    ".apm",
    ".arj",
    ".chm",
    ".cpio",
    ".cramfs",
    ".deb",
    ".dmg",
    ".fat",
    ".hfs",
    ".lzh",
    ".lzma",
    ".mbr",
    ".msi",
    ".mslz",
    ".nsis",
    ".ntfs",
    ".rpm",
    ".squashfs",
    ".udf",
    ".vhd",
    ".xar",
    ".zst",
    ".zstd",
    ".cbz",
    ".apfs",
    ".ar",
    ".qcow",
    ".macho",
    ".exe",
    ".dll",
    ".sys",
    ".pmd",
    ".swf",
    ".swfc",
    ".simg",
    ".vdi",
    ".vhdx",
    ".vmdk",
    ".gzip",
    ".lzma86",
    ".sha256",
    ".sha512",
    ".sha224",
    ".sha384",
    ".sha1",
    ".md5",
    ".crc32",
    ".crc64",
]


FIRST_SPLIT_REGEX = (
    r"\.part0*1\.rar$|\.rar\.0*1$|\.7z\.0*1$|\.zip\.0*1$|"
    r"^(?!.*\.part\d+\.rar$).*\.rar$"
)

SPLIT_REGEX = (
    r"\.\w+\.\d{3}$|\.r\d+$|\.rar\.\d+$|\.7z\.\d+$|\.z\d+$|"
    r"\.zip\.\d+$|\.part\d+\.rar$"
)


def is_first_archive_split(file):
    return bool(re_search(FIRST_SPLIT_REGEX, file.lower(), I))


def is_archive(file):
    return file.strip().lower().endswith(tuple(ARCH_EXT))


def is_archive_split(file):
    return bool(re_search(SPLIT_REGEX, file.lower(), I))


async def clean_target(opath):
    if await aiopath.exists(opath):
        LOGGER.info(f"Cleaning Target: {opath}")
        try:
            if await aiopath.isdir(opath):
                await aiormtree(opath, ignore_errors=True)
            else:
                await remove(opath)
        except Exception as e:
            LOGGER.error(str(e))


async def clean_download(opath):
    if await aiopath.exists(opath):
        LOGGER.info(f"Cleaning Download: {opath}")
        try:
            await aiormtree(opath, ignore_errors=True)
        except Exception as e:
            LOGGER.error(str(e))


async def clean_all():
    await TorrentManager.remove_all()
    LOGGER.info("Cleaning Download Directory")
    await cmd_exec(["rm", "-rf", DOWNLOAD_DIR])
    await aiomakedirs(DOWNLOAD_DIR, exist_ok=True)


async def clean_unwanted(opath):
    LOGGER.info(f"Cleaning unwanted files/folders: {opath}")
    for dirpath, _, files in await sync_to_async(walk, opath, topdown=False):
        for filee in files:
            f_path = ospath.join(dirpath, filee)
            if filee.strip().endswith(".parts") and filee.startswith("."):
                await remove(f_path)
        if dirpath.strip().endswith(".unwanted"):
            await aiormtree(dirpath, ignore_errors=True)
    for dirpath, _, files in await sync_to_async(walk, opath, topdown=False):
        if not await listdir(dirpath):
            await rmdir(dirpath)


async def check_storage_threshold(size, threshold, io_task=False, alloc=False):
    free = (await sync_to_async(disk_usage, DOWNLOAD_DIR)).free
    return free >= (threshold + (size * (2 if io_task else 1) if not alloc else 0))


async def get_path_size(opath):
    total_size = 0
    if await aiopath.isfile(opath):
        if await aiopath.islink(opath):
            opath = await aioreadlink(opath)
        return await aiopath.getsize(opath)
    for root, _, files in await sync_to_async(walk, opath):
        for f in files:
            abs_path = ospath.join(root, f)
            if await aiopath.islink(abs_path):
                abs_path = await aioreadlink(abs_path)
            total_size += await aiopath.getsize(abs_path)
    return total_size


async def count_files_and_folders(opath):
    total_files = 0
    total_folders = 0
    for _, dirs, files in await sync_to_async(walk, opath):
        total_files += len(files)
        total_folders += len(dirs)
    return total_folders, total_files


def get_base_name(orig_path):
    extension = next(
        (ext for ext in ARCH_EXT if orig_path.strip().lower().endswith(ext)), ""
    )
    if extension != "":
        return re_split(f"{extension}$", orig_path, maxsplit=1, flags=I)[0]
    else:
        raise NotSupportedExtractionArchive("File format not supported for extraction")


async def create_recursive_symlink(source, destination):
    if ospath.isdir(source):
        await aiomakedirs(destination, exist_ok=True)
        for item in await listdir(source):
            item_source = ospath.join(source, item)
            item_dest = ospath.join(destination, item)
            await create_recursive_symlink(item_source, item_dest)
    elif ospath.isfile(source):
        try:
            await symlink(source, destination)
        except FileExistsError:
            LOGGER.error(f"Shortcut already exists: {destination}")
        except Exception as e:
            LOGGER.error(f"Error creating shortcut for {source}: {e}")


def get_mime_type(file_path):
    if ospath.islink(file_path):
        file_path = readlink(file_path)
    mime = Magic(mime=True)
    mime_type = mime.from_file(file_path)
    mime_type = mime_type or "text/plain"
    return mime_type


async def remove_excluded_files(fpath, ee):
    for root, _, files in await sync_to_async(walk, fpath):
        if root.strip().endswith("/yt-dlp-thumb"):
            continue
        for f in files:
            if f.strip().lower().endswith(tuple(ee)):
                await remove(ospath.join(root, f))


async def move_and_merge(source, destination, mid):
    if not await aiopath.exists(destination):
        await aiomakedirs(destination, exist_ok=True)
    for item in await listdir(source):
        item = item.strip()
        src_path = f"{source}/{item}"
        dest_path = f"{destination}/{item}"
        if await aiopath.isdir(src_path):
            if await aiopath.exists(dest_path):
                await move_and_merge(src_path, dest_path, mid)
            else:
                await move(src_path, dest_path)
        else:
            if item.endswith((".aria2", ".!qB")):
                continue
            if await aiopath.exists(dest_path):
                dest_path = f"{destination}/{mid}-{item}"
            await move(src_path, dest_path)


async def join_files(opath):
    await sync_to_async(_join_files, Path(opath))


def _join_files(folder):
    groups = {}
    for part in folder.iterdir():
        name, _, suffix = part.name.rpartition(".")
        if name and re_search(r"^[0-9]{2,}\Z", suffix):
            groups.setdefault(name, {}).setdefault(len(suffix), []).append((int(suffix), part))

    for name, widths in groups.items():
        candidates = [
            parts for parts in widths.values()
            if any(index == 2 for index, _ in parts)
            or (len(parts) > 1 and any(index == 1 for index, _ in parts))
        ]
        if not candidates:
            continue
        if len(candidates) != 1:
            raise OSError(f"Ambiguous split-file numbering for {name}")
        numbered = candidates[0]
        numbered.sort()
        if len(numbered) > 1 and numbered[1][0] == 2 and get_mime_type(
            str(numbered[1][1].resolve())
        ) in ("application/x-7z-compressed", "application/zip"):
            continue
        if any(index != expected for expected, (index, _) in enumerate(numbered, 1)):
            raise OSError(f"Split file {name} has missing or duplicate parts")

        target = folder / name
        if ospath.lexists(target):
            raise FileExistsError(f"Join output already exists: {target}")
        with TemporaryDirectory(prefix=".join-", dir=folder) as temp:
            staged = Path(temp) / "merged"
            native_join = getattr(rust_core(), "join_files", None)
            if native_join is not None:
                native_join([part for _, part in numbered], staged)
            else:
                with staged.open("wb") as output:
                    for _, part in numbered:
                        with part.open("rb") as source:
                            copyfileobj(source, output, 1024 * 1024)
                    output.flush()
                    fsync(output.fileno())
            # Publish atomically without replacing an output created by another job.
            link(staged, target)

        for _, part in numbered:
            part.unlink(missing_ok=True)
        LOGGER.info("Joined %s", name)


async def split_file(f_path, split_size, listener):
    out_path = f"{f_path}."
    if listener.is_cancelled:
        return False
    # pread parallel split
    listener.subproc = await create_subprocess_exec(
        "split",
        "--numeric-suffixes=1",
        "--suffix-length=3",
        f"--bytes={split_size}",
        f_path,
        out_path,
        stderr=PIPE,
    )
    _, stderr = await listener.subproc.communicate()
    code = listener.subproc.returncode
    if listener.is_cancelled:
        return False
    if code == -9:
        listener.is_cancelled = True
        return False
    elif code != 0:
        try:
            stderr = stderr.decode().strip()
        except Exception:
            stderr = "Unable to decode the error!"
        LOGGER.error(f"{stderr}. Split Document: {f_path}")
        part_prefix = ospath.basename(out_path)
        part_dir = ospath.dirname(f_path) or "."
        for part in await listdir(part_dir):
            if re_search(rf"^{escape(part_prefix)}\d{{3}}$", part):
                await remove(ospath.join(part_dir, part))
        return False
    return True


class SevenZ:
    def __init__(self, listener):
        self._listener = listener
        self._processed_bytes = 0
        self._percentage = "0%"

    @property
    def processed_bytes(self):
        return self._processed_bytes

    @property
    def progress(self):
        return self._percentage

    async def _sevenz_progress(self):
        pattern = r"(\d+)\s+bytes|Total Physical Size\s*=\s*(\d+)"
        while not (
            self._listener.subproc.returncode is not None
            or self._listener.is_cancelled
            or self._listener.subproc.stdout.at_eof()
        ):
            try:
                line = await wait_for(self._listener.subproc.stdout.readline(), 2)
            except Exception:
                break
            line = line.decode().strip()
            if match := re_search(pattern, line):
                self._listener.subsize = int(match[1] or match[2])
        # 7z redraws progress in place (backspaces, no newlines), so read in
        # chunks and keep only the latest "NN%". Reading byte-by-byte with a
        # sleep could not keep up and let the pipe fill, stalling 7z.
        tail = b""
        while not (
            self._listener.is_cancelled
            or self._listener.subproc.returncode is not None
            or self._listener.subproc.stdout.at_eof()
        ):
            try:
                chunk = await wait_for(self._listener.subproc.stdout.read(4096), 60)
            except Exception:
                break
            if not chunk:
                break
            data = tail + chunk
            percents = re_findall(rb"(\d{1,3})%", data)
            if percents:
                try:
                    value = min(int(percents[-1]), 100)
                    self._percentage = f"{value}%"
                    self._processed_bytes = (value / 100) * self._listener.subsize
                except Exception:
                    self._processed_bytes = 0
                    self._percentage = "0%"
            # Keep a short tail so a "NN%" split across reads is still seen.
            tail = data[-8:]

        self._processed_bytes = 0
        self._percentage = "0%"

    async def extract(self, f_path, t_path, pswd):
        cmd = ["7z", "x"]
        if pswd:
            cmd.append(f"-p{pswd}")
        cmd.extend(
            [
                f_path,
                f"-o{t_path}",
                "-aot",
                "-xr!@PaxHeader",
                "-bsp1",
                "-bse1",
                "-bb3",
            ]
        )
        if self._listener.is_cancelled:
            return False
        self._listener.subproc = await create_subprocess_exec(
            *cmd,
            stdout=PIPE,
            stderr=PIPE,
        )
        await self._sevenz_progress()
        _, stderr = await self._listener.subproc.communicate()
        code = self._listener.subproc.returncode
        if self._listener.is_cancelled:
            return False
        if code == -9:
            self._listener.is_cancelled = True
            return False
        elif code != 0:
            try:
                stderr = stderr.decode().strip()
            except Exception:
                stderr = "Unable to decode the error!"
            LOGGER.error(f"{stderr}. Unable to extract archive!. Path: {f_path}")
        return code

    async def zip(self, dl_path, up_path, pswd):
        size = await get_path_size(dl_path)
        if self._listener.equal_splits:
            # max(1, ...) keeps zero-byte content from dividing by zero.
            parts = max(1, -(-size // self._listener.split_size))
            split_size = (size // parts) + (size % parts)
        else:
            split_size = self._listener.split_size
        cmd = ["7z"]
        if self._listener.is_leech and int(size) > self._listener.split_size:
            cmd.append(f"-v{split_size}b")
            LOGGER.info(f"Zip: orig_path: {dl_path}, zip_path: {up_path}.0*")
        else:
            LOGGER.info(f"Zip: orig_path: {dl_path}, zip_path: {up_path}")
        cmd.extend(["a", "-mx=0", "-mmt=on"])
        if pswd:
            cmd.append(f"-p{pswd}")
        cmd.extend([up_path, dl_path, "-bsp1", "-bse1", "-bb3"])
        if self._listener.is_cancelled:
            return False
        self._listener.subproc = await create_subprocess_exec(
            *cmd, stdout=PIPE, stderr=PIPE
        )
        await self._sevenz_progress()
        _, stderr = await self._listener.subproc.communicate()
        code = self._listener.subproc.returncode
        if self._listener.is_cancelled:
            return False
        if code == -9:
            self._listener.is_cancelled = True
            return False
        elif code == 0:
            await clean_target(dl_path)
            return up_path
        else:
            if await aiopath.exists(up_path):
                await remove(up_path)
            try:
                stderr = stderr.decode().strip()
            except Exception:
                stderr = "Unable to decode the error!"
            LOGGER.error(f"{stderr}. Unable to zip this path: {dl_path}")
            return False
