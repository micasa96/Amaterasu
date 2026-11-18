use pyo3::exceptions::PyIOError;
use pyo3::prelude::*;
use pyo3::types::PyModule;
use regex::Regex;
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::{self, Read, Write};
use std::path::PathBuf;
use std::sync::LazyLock;

mod crypto_ige;
mod media_probe;

fn patterns(values: &[&str]) -> Vec<Regex> {
    values
        .iter()
        .map(|value| Regex::new(value).unwrap())
        .collect()
}

static EPISODES: LazyLock<Vec<Regex>> = LazyLock::new(|| {
    patterns(&[
        r"(?i)S(\d+)(?:E|EP)(\d+)",
        r"(?i)S(\d+)[\s-]*(?:E|EP)(\d+)",
        r"(?i)Season\s*(\d+)\s*Episode\s*(\d+)",
        r"(?i)\[S(\d+)\]\[E(\d+)\]",
        r"(?i)S(\d+)[^\d]*(\d+)",
        r"(?i)(?:E|EP|Episode)\s*(\d+)",
    ])
});
static QUALITIES: LazyLock<Vec<Regex>> = LazyLock::new(|| {
    patterns(&[
        r"(?i)\b(\d{3,4}[pi])\b",
        r"(?i)\b(4k|2160p)\b",
        r"(?i)\b(2k|1440p)\b",
        r"(?i)\b(HDRip|HDTV|WEBRip|WEB-DL|BDRip|BluRay)\b",
        r"(?i)\b(4kX264|4kx265|x264|x265|HEVC)\b",
        r"(?i)\[(\d{3,4}[pi])\]",
    ])
});
static CLEANUP: LazyLock<Vec<Regex>> =
    LazyLock::new(|| patterns(&[r"\[.*?\]", r"\(.*?\)", r"[_\-.]+", r"\b(19|20)\d{2}\b"]));

type Release = (Option<String>, Option<String>, String, String);

fn pad(value: &str) -> String {
    if value.chars().count() == 1 {
        format!("0{value}")
    } else {
        value.to_owned()
    }
}

fn parse(filename: &str, stem: &str) -> Release {
    let (mut season, mut episode) = (None, None);
    for rule in EPISODES.iter() {
        if let Some(captures) = rule.captures(filename) {
            if let Some(second) = captures.get(2) {
                season = Some(pad(&captures[1]));
                episode = Some(pad(second.as_str()));
            } else {
                episode = Some(pad(&captures[1]));
            }
            break;
        }
    }
    let quality = QUALITIES
        .iter()
        .enumerate()
        .find_map(|(index, rule)| {
            rule.captures(filename).map(|captures| match index {
                1 => "4k".to_owned(),
                2 => "2k".to_owned(),
                _ => captures[1].to_owned(),
            })
        })
        .unwrap_or_default();

    let mut title = stem.to_owned();
    for rule in EPISODES.iter().chain(QUALITIES.iter()) {
        if let std::borrow::Cow::Owned(replaced) = rule.replace_all(&title, "") {
            title = replaced;
        }
    }
    for (rule, replacement) in CLEANUP.iter().zip(["", "", " ", ""]) {
        if let std::borrow::Cow::Owned(replaced) = rule.replace_all(&title, replacement) {
            title = replaced;
        }
    }
    (season, episode, quality, title.trim().to_owned())
}

#[pyfunction]
fn parse_release_metadata(py: Python<'_>, filename: &str, stem: &str) -> Release {
    py.detach(|| parse(filename, stem))
}

#[pyfunction]
fn batch_parse_filenames(py: Python<'_>, filenames: Vec<(String, String)>) -> Vec<Release> {
    py.detach(|| {
        filenames
            .iter()
            .map(|(filename, stem)| parse(filename, stem))
            .collect()
    })
}

fn join(parts: Vec<PathBuf>, output: PathBuf) -> io::Result<(u64, String, String)> {
    let mut output = File::create_new(output)?;
    let mut total = 0;
    let mut sha = Sha256::new();
    let mut crc = crc32fast::Hasher::new();
    let mut buffer = vec![0; 1024 * 1024];
    for part in parts {
        let mut input = File::open(part)?;
        loop {
            let len = input.read(&mut buffer)?;
            if len == 0 {
                break;
            }
            let bytes = &buffer[..len];
            output.write_all(bytes)?;
            sha.update(bytes);
            crc.update(bytes);
            total += len as u64;
        }
    }
    output.sync_all()?;
    Ok((
        total,
        format!("{:x}", sha.finalize()),
        format!("{:08X}", crc.finalize()),
    ))
}

#[pyfunction]
fn join_files(py: Python<'_>, parts: Vec<PathBuf>, output: PathBuf) -> PyResult<u64> {
    py.detach(move || -> io::Result<u64> {
        let mut output = File::create_new(output)?;
        let mut total = 0;
        for part in parts {
            total += io::copy(&mut File::open(part)?, &mut output)?;
        }
        output.sync_all()?;
        Ok(total)
    })
    .map_err(|error| PyIOError::new_err(error.to_string()))
}

#[pyfunction]
fn join_and_hash_files(
    py: Python<'_>,
    parts: Vec<PathBuf>,
    output: PathBuf,
) -> PyResult<(u64, String, String)> {
    py.detach(move || join(parts, output))
        .map_err(|error| PyIOError::new_err(error.to_string()))
}

#[pymodule]
fn amaterasu_rs(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(parse_release_metadata, module)?)?;
    module.add_function(wrap_pyfunction!(batch_parse_filenames, module)?)?;
    module.add_function(wrap_pyfunction!(join_files, module)?)?;
    module.add_function(wrap_pyfunction!(join_and_hash_files, module)?)?;
    module.add_function(wrap_pyfunction!(
        media_probe::probe_container_header,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(crypto_ige::aes256_ige_in_place, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn filename_rules_preserve_template_values() {
        assert_eq!(
            parse(
                "[Team] Show [S02][E3] 1080p.mkv",
                "[Team] Show [S02][E3] 1080p"
            ),
            (
                Some("02".into()),
                Some("03".into()),
                "1080p".into(),
                "Show".into()
            )
        );
        assert_eq!(parse("Show Episode 4 2K", "Show Episode 4 2K").0, None);
    }
}
