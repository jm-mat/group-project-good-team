`timescale 1ns / 1ps

module argmax (
    // NN logits from hls4ml (ap_fixed is signed two's complement).
    // Width must match layer8_out_*_V in top.v / glue_logic.v (24 bits).
    // Declared signed so >= compares by value: without it a negative logit
    // has its MSB set and looks larger than any positive one.
    input  wire signed [23:0] out0,
    input  wire signed [23:0] out1,
    input  wire signed [23:0] out2,
    output reg         [1:0]  pred_class
);
    // Select the index of largest of the three inference values
    // (ties go to the lowest index)
    always @(*) begin
        if (out0 >= out1 && out0 >= out2)
            pred_class = 2'd0;
        else if (out1 >= out0 && out1 >= out2)
            pred_class = 2'd1;
        else
            pred_class = 2'd2;
    end
endmodule
