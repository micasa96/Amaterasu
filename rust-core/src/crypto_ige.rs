use aes::cipher::{generic_array::GenericArray, BlockDecrypt, BlockEncrypt, KeyInit};
use aes::Aes256;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::sync::critical_section::with_critical_section;
use pyo3::types::{PyByteArray, PyByteArrayMethods};

fn xor(mut left: [u8; 16], right: [u8; 16]) -> [u8; 16] {
    for (byte, other) in left.iter_mut().zip(right) {
        *byte ^= other;
    }
    left
}

fn crypt(data: &mut [u8], cipher: &Aes256, iv: &[u8; 32], decrypt: bool) {
    let (mut previous_cipher, mut previous_plain) =
        (iv[..16].try_into().unwrap(), iv[16..].try_into().unwrap());
    for chunk in data.chunks_exact_mut(16) {
        let input: [u8; 16] = chunk.try_into().unwrap();
        if decrypt {
            let mut block = GenericArray::from(xor(input, previous_plain));
            cipher.decrypt_block(&mut block);
            previous_plain = xor(block.into(), previous_cipher);
            previous_cipher = input;
            chunk.copy_from_slice(&previous_plain);
        } else {
            let mut block = GenericArray::from(xor(input, previous_cipher));
            cipher.encrypt_block(&mut block);
            previous_cipher = xor(block.into(), previous_plain);
            previous_plain = input;
            chunk.copy_from_slice(&previous_cipher);
        }
    }
}

#[pyfunction]
pub fn aes256_ige_in_place(
    data: &Bound<'_, PyByteArray>,
    key: &[u8],
    iv: &[u8],
    decrypt: bool,
) -> PyResult<()> {
    let cipher = Aes256::new_from_slice(key)
        .map_err(|_| PyValueError::new_err("expected a 32-byte AES key"))?;
    let iv: &[u8; 32] = iv
        .try_into()
        .map_err(|_| PyValueError::new_err("expected a 32-byte IGE IV"))?;
    let ok = with_critical_section(data, || {
        if data.len() % 16 != 0 {
            return false;
        }
        // The interpreter remains attached and the bytearray stays locked until the slice is dropped.
        crypt(unsafe { data.as_bytes_mut() }, &cipher, iv, decrypt);
        true
    });
    if ok {
        Ok(())
    } else {
        Err(PyValueError::new_err(
            "AES-IGE data must contain whole blocks",
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn encrypts_and_decrypts_warpcrypto_vector() {
        let cipher = Aes256::new_from_slice(&(0_u8..32).collect::<Vec<_>>()).unwrap();
        let plain: Vec<u8> = (32..64).collect();
        let mut data = plain.clone();
        crypt(&mut data, &cipher, &[0; 32], false);
        assert_eq!(
            data,
            [
                0x61, 0xa6, 0x93, 0x6e, 0x4e, 0x8f, 0x10, 0x1c, 0x1c, 0xc1, 0xf9, 0x93, 0xb5, 0x42,
                0xa0, 0xd4, 0x2f, 0x4f, 0x8e, 0xb2, 0xb9, 0xa9, 0x55, 0x1c, 0xc6, 0xac, 0xb9, 0x94,
                0x34, 0x01, 0xdf, 0x43,
            ]
        );
        crypt(&mut data, &cipher, &[0; 32], true);
        assert_eq!(data, plain);
    }
}
