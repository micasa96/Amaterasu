use pyo3::prelude::*;

type Tracks = Vec<(&'static str, String)>;

fn mp4_box(input: &[u8]) -> Option<(&[u8], &[u8], &[u8])> {
    let short = u32::from_be_bytes(input.get(..4)?.try_into().ok()?);
    let kind = input.get(4..8)?;
    let (size, header) = match short {
        0 => return None,
        1 => (u64::from_be_bytes(input.get(8..16)?.try_into().ok()?), 16),
        _ => (short.into(), 8),
    };
    let size = usize::try_from(size).ok()?;
    Some((kind, input.get(header..size)?, input.get(size..)?))
}

fn find_box<'a>(mut input: &'a [u8], name: &[u8]) -> Option<&'a [u8]> {
    while !input.is_empty() {
        let (kind, body, rest) = mp4_box(input)?;
        if kind == name {
            return Some(body);
        }
        input = rest;
    }
    None
}

fn mp4_tracks(bytes: &[u8]) -> Option<Tracks> {
    let mut movie = find_box(bytes, b"moov")?;
    let mut tracks = Vec::new();
    while !movie.is_empty() {
        let (kind, track, rest) = mp4_box(movie)?;
        movie = rest;
        if kind != b"trak" {
            continue;
        }
        let media = find_box(track, b"mdia")?;
        let handler = find_box(media, b"hdlr")?.get(8..12)?;
        let kind = match handler {
            b"vide" => "video",
            b"soun" => "audio",
            b"text" | b"sbtl" | b"subt" => "subtitle",
            _ => return None,
        };
        let samples = find_box(find_box(media, b"minf")?, b"stbl")?;
        let descriptions = find_box(samples, b"stsd")?;
        if descriptions.get(4..8)? != [0, 0, 0, 1] {
            return None;
        }
        let (codec, _, _) = mp4_box(descriptions.get(8..)?)?;
        tracks.push((kind, std::str::from_utf8(codec).ok()?.to_owned()));
    }
    Some(tracks)
}

fn vint(bytes: &[u8], id: bool) -> Option<(u64, usize)> {
    let marker = *bytes.first()?;
    if marker == 0 || (id && marker < 0x10) {
        return None;
    }
    let width = marker.leading_zeros() as usize + 1;
    let field = bytes.get(..width)?;
    let mut value = u64::from(if id {
        field[0]
    } else {
        field[0] & (0xff_u16 >> width) as u8
    });
    for byte in &field[1..] {
        value = value << 8 | u64::from(*byte);
    }
    Some((value, width))
}

fn ebml_header(bytes: &[u8]) -> Option<(u64, Option<usize>, &[u8])> {
    let (id, id_len) = vint(bytes, true)?;
    let (size, size_len) = vint(bytes.get(id_len..)?, false)?;
    let size = if size == (1_u64 << (size_len * 7)) - 1 {
        None
    } else {
        Some(usize::try_from(size).ok()?)
    };
    Some((id, size, bytes.get(id_len + size_len..)?))
}

fn ebml_element(bytes: &[u8]) -> Option<(u64, &[u8], &[u8])> {
    let (id, size, rest) = ebml_header(bytes)?;
    let size = size?;
    Some((id, rest.get(..size)?, rest.get(size..)?))
}

fn find_element(mut input: &[u8], target: u64) -> Option<&[u8]> {
    while !input.is_empty() {
        let (id, body, rest) = ebml_element(input)?;
        if id == target {
            return Some(body);
        }
        input = rest;
    }
    None
}

fn mkv_tracks(bytes: &[u8]) -> Option<Tracks> {
    let (id, header, mut rest) = ebml_element(bytes)?;
    if id != 0x1a45dfa3 || !matches!(find_element(header, 0x4282)?, b"matroska" | b"webm") {
        return None;
    }
    let segment = loop {
        let (id, len, data) = ebml_header(rest)?;
        if id == 0x18538067 {
            break &data[..len.unwrap_or(data.len()).min(data.len())];
        }
        rest = data.get(len?..)?;
    };
    let mut entries = find_element(segment, 0x1654ae6b)?;
    let mut tracks = Vec::new();
    while !entries.is_empty() {
        let (id, body, rest) = ebml_element(entries)?;
        entries = rest;
        if id != 0xae {
            continue;
        }
        let kind = match find_element(body, 0x83)? {
            [1] => "video",
            [2] => "audio",
            [17] => "subtitle",
            _ => return None,
        };
        let codec = std::str::from_utf8(find_element(body, 0x86)?).ok()?;
        tracks.push((kind, codec.to_owned()));
    }
    Some(tracks)
}

#[pyfunction]
pub fn probe_container_header(py: Python<'_>, bytes: &[u8]) -> Option<(&'static str, Tracks)> {
    py.detach(|| {
        let bytes = bytes.get(..bytes.len().min(64 * 1024))?;
        let (container, tracks) = if bytes.starts_with(&[0x1a, 0x45, 0xdf, 0xa3]) {
            ("matroska", mkv_tracks(bytes)?)
        } else {
            ("mp4", mp4_tracks(bytes)?)
        };
        (!tracks.is_empty()).then_some((container, tracks))
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn truncated_and_oversize_headers_fail_closed() {
        assert!(mp4_tracks(b"\0\0\0\xffmoov").is_none());
        assert!(mkv_tracks(b"\x1a\x45\xdf\xa3\xff").is_none());
        assert!(vint(&[0], false).is_none());
        assert_eq!(vint(&[1, 0, 0, 0, 0, 0, 0, 1], false), Some((1, 8)));
    }
}
