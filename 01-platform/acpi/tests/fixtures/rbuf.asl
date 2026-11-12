DefinitionBlock ("", "DSDT", 2, "TEST", "FIXTURE", 0x00000001)
{
    Name (RBUF, Buffer (0x40)
    {
        0x00
    })
    Method (SHOW, 0, NotSerialized)
    {
        CreateField (RBUF, 0xD0, 0x190, DATA)
    }
}
