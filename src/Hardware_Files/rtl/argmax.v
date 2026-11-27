`timescale 1ns / 1ps

module argmax (
    input  wire [24:0] out0,
    input  wire [24:0] out1,
    input  wire [24:0] out2,
    output reg  [1:0]  pred_class
);
    // Select the index of largest of the three inference values
    always @(*) begin
        if (out0 >= out1 && out0 >= out2)
            pred_class = 2'd0;
        else if (out1 >= out0 && out1 >= out2)
            pred_class = 2'd1;
        else
            pred_class = 2'd2;
    end
endmodule
