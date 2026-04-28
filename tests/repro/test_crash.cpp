// Minimal test to find which component crashes in IC.SchLib
// Build: g++ -std=c++17 -I kicad-9.0/thirdparty/compoundfilereader -o /tmp/test_ic test_crash.cpp
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#include <map>
#include <stdexcept>
#include <fstream>
#include <algorithm>

#include "compoundfilereader.h"
#include "utf.h"

// Minimal ALTIUM_BINARY_READER (same as KiCad 9)
class ALTIUM_BINARY_READER {
public:
    ALTIUM_BINARY_READER(const std::string& binaryData) : m_data(binaryData), m_position(0) {}

    int32_t ReadInt32() {
        if (m_position + sizeof(int32_t) > m_data.size())
            throw std::out_of_range("ALTIUM_BINARY_READER: out of range");
        int32_t value = *reinterpret_cast<const int32_t*>(&m_data[m_position]);
        m_position += sizeof(int32_t);
        return value;
    }

    int16_t ReadInt16() {
        if (m_position + sizeof(int16_t) > m_data.size())
            throw std::out_of_range("ALTIUM_BINARY_READER: out of range");
        int16_t value = *reinterpret_cast<const int16_t*>(&m_data[m_position]);
        m_position += sizeof(int16_t);
        return value;
    }

    uint8_t ReadByte() {
        if (m_position + sizeof(uint8_t) > m_data.size())
            throw std::out_of_range("ALTIUM_BINARY_READER: out of range");
        uint8_t value = *reinterpret_cast<const uint8_t*>(&m_data[m_position]);
        m_position += sizeof(uint8_t);
        return value;
    }

    std::string ReadShortPascalString() {
        uint8_t length = ReadByte();
        if (m_position + length > m_data.size())
            throw std::out_of_range("ALTIUM_BINARY_READER: out of range");
        std::string s(&m_data[m_position], &m_data[m_position + length]);
        m_position += length;
        return s;
    }

    std::string ReadFullPascalString() {
        uint32_t length = ReadInt32();
        if (m_position + length > m_data.size())
            throw std::out_of_range("ALTIUM_BINARY_READER: out of range");
        std::string s(&m_data[m_position], &m_data[m_position + length]);
        m_position += length;
        return s;
    }

    size_t remaining() const { return m_data.size() - m_position; }

private:
    const std::string& m_data;
    size_t m_position;
};

// Simulate ReadProperties binary path
struct Record {
    bool is_binary;
    std::string data;
};

std::vector<Record> readAllRecords(const char* stream_data, size_t stream_size) {
    std::vector<Record> records;
    size_t pos = 0;
    while (pos + 4 <= stream_size) {
        uint32_t raw_length;
        memcpy(&raw_length, stream_data + pos, 4);
        pos += 4;
        bool is_binary = (raw_length & 0xff000000) != 0;
        uint32_t length = raw_length & 0x00ffffff;
        if (length == 0) continue;
        if (length > stream_size - pos) break;
        const char* start = stream_data + pos;
        pos += length;
        bool hasNullByte = start[length - 1] == '\0';
        size_t effective_len = length - (hasNullByte ? 1 : 0);
        records.push_back({is_binary, std::string(start, effective_len)});
    }
    return records;
}

void parseBinaryPin(const std::string& binaryData, int pin_index) {
    ALTIUM_BINARY_READER binreader(binaryData);
    
    int32_t recordId = binreader.ReadInt32();
    if (recordId != 2) {
        throw std::runtime_error("Binary record missing PIN record (got " + std::to_string(recordId) + ")");
    }
    binreader.ReadByte(); // unknown
    binreader.ReadInt16(); // ownerPartId
    binreader.ReadByte(); // displayMode
    binreader.ReadByte(); // innerEdge
    binreader.ReadByte(); // outerEdge
    binreader.ReadByte(); // inner
    binreader.ReadByte(); // outer
    binreader.ReadShortPascalString(); // TEXT
    binreader.ReadByte(); // unknown
    binreader.ReadByte(); // electrical
    binreader.ReadByte(); // pinConglomerate
    binreader.ReadInt16(); // pinLength
    binreader.ReadInt16(); // locationX
    binreader.ReadInt16(); // locationY
    binreader.ReadInt32(); // color
    binreader.ReadShortPascalString(); // NAME
    binreader.ReadShortPascalString(); // DESIGNATOR
    binreader.ReadShortPascalString(); // SWAPIDGROUP
    binreader.ReadShortPascalString(); // partSeq
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <file.SchLib>\n", argv[0]);
        return 1;
    }

    // Read entire file
    std::ifstream ifs(argv[1], std::ios::binary);
    if (!ifs) {
        fprintf(stderr, "Cannot open %s\n", argv[1]);
        return 1;
    }
    std::vector<char> fileData((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
    ifs.close();

    printf("File size: %zu bytes\n", fileData.size());

    // Parse as compound file
    CFB::CompoundFileReader reader(fileData.data(), fileData.size());

    // Enumerate all entries
    int total_components = 0;
    int total_errors = 0;

    reader.EnumFiles(reader.GetRootEntry(), -1,
        [&](const CFB::COMPOUND_FILE_ENTRY* entry, const CFB::utf16string& dir, int level) -> int {
            if (level != 2) return 0; // Only look at level-2 entries (inside component directories)
            if (!reader.IsStream(entry)) return 0;

            std::wstring entryName = UTF16ToWstring(entry->name, entry->nameLen);
            if (entryName != L"Data") return 0;

            // Get parent directory name
            // The dir parameter contains the path
            std::string dirStr;
            for (auto ch : dir) {
                if (ch < 128) dirStr += (char)ch;
                else dirStr += '?';
            }

            // Read stream content
            size_t streamSize = entry->size;
            std::vector<char> streamData(streamSize);
            reader.ReadFile(entry, 0, streamData.data(), streamSize);

            total_components++;

            // Parse records
            auto records = readAllRecords(streamData.data(), streamSize);

            int pin_index = 0;
            for (auto& rec : records) {
                if (rec.is_binary) {
                    try {
                        parseBinaryPin(rec.data, pin_index);
                        pin_index++;
                    } catch (const std::exception& e) {
                        total_errors++;
                        printf("ERROR: component='%s' pin_index=%d: %s (data_size=%zu)\n",
                               dirStr.c_str(), pin_index, e.what(), rec.data.size());
                        return 0; // continue to next component
                    }
                }
            }
            return 0;
        });

    printf("\nTotal components: %d\n", total_components);
    printf("Total errors: %d\n", total_errors);
    return total_errors > 0 ? 1 : 0;
}
