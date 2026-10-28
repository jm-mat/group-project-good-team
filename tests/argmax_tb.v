`timescale 1ns / 1ps

// Self-checking testbench for argmax.v
//
// The NN (hls4ml, ap_fixed) outputs signed fixed-point logits on 24-bit
// buses. They reach argmax through glue_logic as plain [23:0] wires, so
// this testbench drives them the same way. Values below are raw integers;
// the fixed-point scale doesn't matter for a comparison.
//
// Run with Icarus Verilog (from the repo root):
//   iverilog -o argmax_tb tests/argmax_tb.v src/Verilog/argmax.v
//   vvp argmax_tb
// Or in Vivado: add this file as a simulation source and run behavioral sim.

module argmax_tb;

    reg  [23:0] out0, out1, out2;   // IRRELEVANT, SAFE, UNSAFE
    wire [1:0]  pred_class;

    argmax dut (
        .out0       (out0),
        .out1       (out1),
        .out2       (out2),
        .pred_class (pred_class)
    );

    integer errors = 0;
    integer tests  = 0;

    task check(input integer v0, input integer v1, input integer v2,
               input [1:0] expected, input [8*40-1:0] name);
        begin
            out0 = v0[23:0];
            out1 = v1[23:0];
            out2 = v2[23:0];
            #1;
            tests = tests + 1;
            if (pred_class !== expected) begin
                errors = errors + 1;
                $display("FAIL  %0s: (%0d, %0d, %0d) -> got %0d, expected %0d",
                         name, v0, v1, v2, pred_class, expected);
            end else begin
                $display("pass  %0s: (%0d, %0d, %0d) -> %0d",
                         name, v0, v1, v2, pred_class);
            end
        end
    endtask

    initial begin
        // All positive (worked before the fix too)
        check(   10,   20,    5, 2'd1, "all positive, SAFE wins");
        check(   90,   20,    5, 2'd0, "all positive, IRRELEVANT wins");
        check(   10,   20,   35, 2'd2, "all positive, UNSAFE wins");

        // Mixed signs: a negative logit must never beat a positive one
        check( -100,  300,  -50, 2'd1, "SAFE positive, others negative");
        check( -300, -200,   50, 2'd2, "UNSAFE positive, others negative");
        check(  400, -200, -150, 2'd0, "IRRELEVANT positive, others neg");
        check(    0,   -1,   -1, 2'd0, "zero beats negative");

        // All negative: the least negative wins
        check(   -5,   -1,   -9, 2'd1, "all negative, SAFE least negative");
        check(  -50,  -70,  -20, 2'd2, "all negative, UNSAFE least neg");

        // Range extremes of a signed 24-bit value
        check( 8388607, -8388608, 0, 2'd0, "max positive vs min negative");
        check(-8388608,  0, -8388608, 2'd1, "min negative twice");

        // Ties keep the existing priority: lowest index wins
        check(    7,    7,    7, 2'd0, "three-way tie");
        check(   -3,    5,    5, 2'd1, "SAFE/UNSAFE tie");

        $display("----------------------------------------");
        if (errors == 0) begin
            $display("ALL %0d TESTS PASSED", tests);
            $finish;
        end else begin
            $display("%0d of %0d TESTS FAILED", errors, tests);
            $fatal(1);
        end
    end

endmodule
