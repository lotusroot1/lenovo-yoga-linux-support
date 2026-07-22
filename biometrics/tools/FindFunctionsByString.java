// Ghidra headless script: find every function that references a defined
// string containing any of SEARCH_TERMS, and decompile each one to a text
// file. Generic source-file-substring search - not specific to this
// project's chip, reusable for "what part of this driver actually does X"
// questions on any Windows PE binary already imported into a Ghidra
// project. See ../FINDINGS.md, "Enrollment/matching is match-on-chip"
// section, for how this was used to find the fingerprint sensor's real
// enroll/verify opcodes via a source-file path string ("iohub.c") embedded
// in wbdi.dll's compiled log calls.
//
// Edit SEARCH_TERMS and OUTPUT_PATH below, then run headless, e.g. against
// a fresh temp project (avoids ownership-mismatch issues if the project
// was created on a different OS/session):
//
//   analyzeHeadless /tmp/some_project SomeProjectName \
//     -import /path/to/target.dll \
//     -scriptPath /path/to/this/directory \
//     -postScript FindFunctionsByString.java
//
// @category Analysis

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Data;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.io.PrintWriter;
import java.util.*;

public class FindFunctionsByString extends GhidraScript {

    // Edit these for your own search - substrings to look for in any
    // defined string in the binary (source file paths, log format
    // strings, function-name strings, etc. all show up here if the
    // compiler/linker left them in).
    static final String[] SEARCH_TERMS = {"iohub.c", "cmdout.c"};

    static final String OUTPUT_PATH = "/tmp/found_functions_output.txt";

    public void run() throws Exception {
        PrintWriter out = new PrintWriter(OUTPUT_PATH);

        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        Listing listing = currentProgram.getListing();
        DataIterator strings = listing.getDefinedData(true);

        Set<Function> targets = new LinkedHashSet<>();

        while (strings.hasNext()) {
            Data d = strings.next();
            if (!d.hasStringValue()) continue;
            String val;
            try {
                val = (String) d.getValue();
            } catch (Exception e) {
                continue;
            }
            if (val == null) continue;

            boolean matches = false;
            for (String term : SEARCH_TERMS) {
                if (val.contains(term)) {
                    matches = true;
                    break;
                }
            }
            if (!matches) continue;

            out.println("STRING @ " + d.getAddress() + " : \"" + val + "\"");
            ReferenceIterator refs = d.getReferenceIteratorTo();
            while (refs.hasNext()) {
                Reference r = refs.next();
                Address from = r.getFromAddress();
                Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
                if (f != null) {
                    targets.add(f);
                    out.println("    referenced by " + f.getName() + " @ " + f.getEntryPoint());
                }
            }
        }

        out.println();
        out.println("=== Found " + targets.size() + " functions, decompiling ===");
        out.println();

        for (Function f : targets) {
            out.println("================================================================================");
            out.println("FUNCTION: " + f.getName() + " @ " + f.getEntryPoint());
            out.println("================================================================================");
            out.println();
            DecompileResults res = decomp.decompileFunction(f, 60, monitor);
            if (res != null && res.decompileCompleted()) {
                out.println(res.getDecompiledFunction().getC());
            } else {
                out.println("(decompile failed)");
            }
            out.println();
        }

        out.close();
        println("Wrote results to " + OUTPUT_PATH);
    }
}
