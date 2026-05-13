`timescale 1ns / 1ps

module seven_seg_driver (
    input  wire       clk,
    input  wire       rst,
    input  wire [1:0] pred_class,
    output reg  [6:0] seg,
    output reg  [3:0] an
);
    always @(posedge clk) begin
        if (rst) begin
            an <= 4'b1110; // enable digit 0 (active low)
        end else begin
            an <= 4'b1110;
        end
    end
    
    // Only display 0,1,2 for the 3 inference classes
    always @(*) begin
        case (pred_class)
            2'd0: seg = 7'b1000000; // "0"
            2'd1: seg = 7'b1111001; // "1"
            2'd2: seg = 7'b0100100; // "2"
            default: seg = 7'b1111111; // blank
        endcase
    end
endmodule