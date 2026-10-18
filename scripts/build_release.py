"""Build a Windows installer, portable ZIP and SHA256 checksums."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def run(arguments, **kwargs):
    subprocess.run([str(arg) for arg in arguments], cwd=ROOT, check=True, **kwargs)


def find_iscc():
    if os.environ.get("ISCC_PATH"):
        return os.environ["ISCC_PATH"]
    if shutil.which("ISCC"):
        return shutil.which("ISCC")
    for version in ("7", "6"):
        for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            base = Path(os.environ.get(variable, "C:/Program Files (x86)"))
            for directory in (base, base / "Programs"):
                candidate = directory / f"Inno Setup {version}" / "ISCC.exe"
                if candidate.is_file():
                    return str(candidate)
    raise SystemExit("Instale o Inno Setup ou configure ISCC_PATH com o caminho de ISCC.exe.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iscc", default=None)
    parser.add_argument("--tag", help="Verify the release tag matches pyproject.toml")
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if args.tag and args.tag != f"v{version}":
        raise SystemExit(f"Tag {args.tag} não corresponde à versão v{version}.")
    iscc = args.iscc or find_iscc()
    work = ROOT / "build/release"
    artifacts = ROOT / "dist/release"
    work.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    numbers = tuple(int(part) for part in version.split(".")) + (0,)
    version_file = work / "version.txt"
    version_file.write_text(
        "VSVersionInfo(ffi=FixedFileInfo(filevers=" + repr(numbers) + ", prodvers=" + repr(numbers)
        + ", mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)), "
        "kids=[StringFileInfo([StringTable('041604B0', ["
        "StringStruct('CompanyName', 'SamuelASDev'),"
        "StringStruct('FileDescription', 'Entre Terras - Contador de mortes'),"
        f"StringStruct('FileVersion', '{version}'),"
        "StringStruct('InternalName', 'EntreTerras'),"
        "StringStruct('OriginalFilename', 'EntreTerras.exe'),"
        "StringStruct('ProductName', 'Entre Terras'),"
        f"StringStruct('ProductVersion', '{version}')"
        "]) ]), VarFileInfo([VarStruct('Translation', [1046, 1200])])])",
        encoding="utf-8",
    )
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    environment = dict(os.environ, ENTRE_TERRAS_VERSION_FILE=str(version_file))
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", work / "dist",
         "--workpath", work / "work", "EntreTerras.spec"], env=environment)
    distribution = work / "dist/EntreTerras"
    executable = distribution / "EntreTerras.exe"
    shutil.copy2(ROOT / "installer/leia-me.txt", distribution / "LEIA-ME.txt")
    thumbprint = os.environ.get("WINDOWS_SIGN_THUMBPRINT")
    compiler = [iscc, f"/DAppVersion={version}", f"/DSourceDir={distribution}",
                f"/DArtifactsDir={artifacts}"]
    if thumbprint:
        signtool = os.environ.get("SIGNTOOL_PATH") or shutil.which("signtool")
        if not signtool:
            raise SystemExit("Assinatura solicitada, mas signtool.exe não foi encontrado.")
        sign = [signtool, "sign", "/sha1", thumbprint, "/fd", "SHA256", "/tr",
                os.environ.get("WINDOWS_TIMESTAMP_URL", "http://timestamp.digicert.com"), "/td", "SHA256"]
        run([*sign, executable])
        sign_command = "$q" + str(signtool) + "$q " + subprocess.list2cmdline(sign[1:]) + " $f"
        compiler += ["/DSignedBuild", "/SReleaseSign=" + sign_command]
    else:
        print("Build sem assinatura Authenticode: o Windows pode mostrar avisos de publicador.", flush=True)
    run([*compiler, ROOT / "installer/EntreTerras.iss"])
    setup = artifacts / f"EntreTerras-{version}-Setup-x64.exe"
    portable = Path(shutil.make_archive(str(artifacts / f"EntreTerras-{version}-Portable-x64"),
                                        "zip", root_dir=distribution.parent, base_dir=distribution.name))
    sums = artifacts / "SHA256SUMS.txt"
    checksums = []
    for path in (setup, portable):
        with path.open("rb") as file:
            checksums.append(f"{hashlib.file_digest(file, 'sha256').hexdigest()}  {path.name}\n")
    sums.write_text("".join(checksums), encoding="utf-8")
    print(f"Pronto: {artifacts}")


if __name__ == "__main__":
    main()
