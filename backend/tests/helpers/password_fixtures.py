"""Fixed, non-secret samples; tests never generate new legacy hashes."""

ADMIN_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=1$/yVlkl4mup9mLEnya1zvVg$"
    "6+FHMvRZih7FUYiPlAzyVzWLFlOrM5ERfsAhYbtFnzo"
)
TEST_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=1$WDoKZWPIc6QmDBbMdCiOzA$"
    "Z7UN0BJQixB6iNjztXhrhu99sDb93AiiKzzCS4v2qSQ"
)
LEGACY_HASH = "pbkdf2_sha256$310000$dGVzdC1zYWx0$eNdfqLxzN-uOuuLlTuYn1e628QshuiidqIFPH96kBi0"
