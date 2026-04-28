// LD_PRELOAD hook that aborts on ALTIUM_BINARY_READER throw for GDB
// Build: g++ -shared -fPIC -o /tmp/catch_abort.so catch_abort.cpp -ldl -lpthread
#include <cxxabi.h>
#include <dlfcn.h>
#include <typeinfo>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <execinfo.h>

static int throw_count = 0;

extern "C" void __cxa_throw(void* thrown_exception, std::type_info* tinfo, void (*dest)(void*)) {
    throw_count++;
    
    const char* name = tinfo->name();
    
    // Try to get what() — if it's std::exception derived
    try {
        // The thrown object starts at thrown_exception
        std::exception* e = reinterpret_cast<std::exception*>(thrown_exception);
        const char* what = e->what();
        
        if (what && strstr(what, "ALTIUM_BINARY_READER") != nullptr) {
            fprintf(stderr, "\n=== ALTIUM_BINARY_READER throw #%d ===\n", throw_count);
            fprintf(stderr, "what(): %s\n", what);
            
            // Print backtrace
            void* bt[30];
            int n = backtrace(bt, 30);
            char** syms = backtrace_symbols(bt, n);
            for (int i = 0; i < n; i++)
                fprintf(stderr, "  [%d] %s\n", i, syms[i]);
            free(syms);
            
            fprintf(stderr, "=== ABORTING for GDB analysis ===\n");
            fflush(stderr);
            abort();
        }
    } catch (...) {}
    
    // Forward to real __cxa_throw
    typedef void (*cxa_throw_t)(void*, std::type_info*, void (*)(void*));
    static cxa_throw_t real_throw = nullptr;
    if (!real_throw) {
        real_throw = (cxa_throw_t)dlsym(RTLD_NEXT, "__cxa_throw");
    }
    real_throw(thrown_exception, tinfo, dest);
    __builtin_unreachable();
}
